# Agent Name Display in Plan Steps

## Overview

This document summarizes the changes made to display agent names in front of each task when the planner creates a plan in the frontend application.

## Problem Statement

Previously, when the multi-agent planner created a plan, the plan steps displayed only the task descriptions without indicating which agent would perform each task. This made it difficult for users to understand the agent assignment for each step.

**Before:**
```
1. Gather industry data
2. Analyze competitor pricing
3. Generate recommendations
```

**After:**
```
1. [EnhancedResearchAgent] Gather industry data
2. [DataAnalysisAgent] Analyze competitor pricing
3. [RecommendationAgent] Generate recommendations
```

## Backend Architecture

### Plan Parsing (`plan_to_mplan_converter.py`)

The backend parser extracts agent names from the plan text and stores them separately:

- **Agent Extraction Methods:**
  - `_try_bold_agent()`: Extracts agent from `**AgentName**` pattern
  - `_try_window_agent()`: Fallback detection in first 25 characters
  - `_extract_agent_and_action()`: Returns tuple of (agent_name, cleaned_action_text)

- **Data Structure:**
  ```python
  MStep(
      agent="EnhancedResearchAgent",  # Agent name stored separately
      action="Gather industry data"    # Clean action text without agent name
  )
  ```

The parser removes the agent name from the action text after extraction, storing it in a separate `agent` field.

## Frontend Changes

### Files Modified

1. **`src/frontend/src/components/content/streaming/StreamingPlanResponse.tsx`**
2. **`src/frontend/src/components/content/PlanPanelRight.tsx`**

### Implementation Details

#### StreamingPlanResponse.tsx

**Location:** Lines 216-228 (step extraction logic)

**Changes:**
```typescript
// Extract agent name from step data
const agent = step.agent || 'System';
const action = step.action || step.cleanAction || '';

// Format: [AgentName] action
const displayText = `[${agent}] ${action.trim()}`;

// Store formatted text
planSteps.push({ 
    type: action.trim().endsWith(':') ? 'heading' : 'substep', 
    text: displayText 
});
```

#### PlanPanelRight.tsx

**Location:** Lines 38-51 (step extraction logic)

**Changes:**
```typescript
return planApprovalRequest.steps.map((step, index) => {
    const action = step.action || step.cleanAction || '';
    const agent = step.agent || 'System';
    const isHeading = action.trim().endsWith(':');
    
    // Format: [AgentName] action
    const displayText = `[${agent}] ${action.trim()}`;

    return {
        text: displayText,
        isHeading,
        key: `${index}-${action.substring(0, 20)}`
    };
}).filter(step => step.text.length > 0);
```

## Display Format

### Chosen Format: `[AgentName]`

The agent name is displayed in square brackets before the action text:
- **Format:** `[AgentName] action description`
- **Example:** `[EnhancedResearchAgent] Gather industry data from multiple sources`

### Alternative Formats Considered

1. **Bold Markdown:** `**AgentName** action` - Not rendered as bold in plain text display
2. **HTML Strong Tags:** `<strong>AgentName</strong> action` - Rendered as literal text instead of styled
3. **Inline Styles:** Separate React elements with `fontWeight: 700` - More complex implementation
4. **Brackets (Selected):** `[AgentName] action` - Clean, simple, and universally visible

## Benefits

1. **Clear Agent Assignment:** Users can immediately see which agent is responsible for each task
2. **Better Understanding:** Improves comprehension of the multi-agent workflow
3. **Enhanced Transparency:** Makes the plan execution strategy more visible
4. **Consistent Display:** Works across all plan display components

## Testing

To verify the changes:

1. Deploy the application with updated frontend code
2. Create a new multi-agent plan request
3. Verify that plan steps display with agent names in brackets
4. Check both the streaming plan response and the plan panel right display

## Future Enhancements

Potential improvements for consideration:

1. **Color Coding:** Different colors for different agent types
2. **Agent Icons:** Visual icons next to agent names
3. **Tooltips:** Hover descriptions explaining each agent's role
4. **Filtering:** Ability to filter plan steps by agent
5. **Bold Styling:** Implement proper React-based bold styling for agent names

## Related Files

- **Backend Parser:** `src/backend/v3/orchestration/helper/plan_to_mplan_converter.py`
- **Plan Prompt:** `src/backend/v3/orchestration/human_approval_manager.py`
- **Frontend Display:** `src/frontend/src/components/content/streaming/StreamingPlanResponse.tsx`
- **Plan Panel:** `src/frontend/src/components/content/PlanPanelRight.tsx`
- **Data Models:** `src/frontend/src/models/` (MPlanData, MStep interfaces)

## Deployment

After making these changes, redeploy the app. The changes will be reflected in the frontend application after the deployment completes.
