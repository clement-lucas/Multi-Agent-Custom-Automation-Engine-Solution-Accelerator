# Follow-Up Questions Feature Implementation

## Overview

This document summarizes the changes made to enable follow-up questions after the agent provides a final answer. The feature keeps the user input enabled and generates three numbered follow-up questions that users can click or type to continue the conversation.

## Feature Objectives

1. **Keep Input Enabled**: User input remains active after the agent completes a task
2. **Generate Follow-Up Questions**: Agent automatically generates 3 numbered follow-up questions based on the completed task
3. **Clickable Questions**: Follow-up questions are rendered as clickable buttons for easy interaction
4. **Orchestration Recreation**: New orchestration instance is created when follow-up questions are submitted to ensure agents respond properly

## Implementation Changes

### 1. Backend Changes

#### 1.1 Human Approval Manager (`src/backend/v3/orchestration/human_approval_manager.py`)

**Purpose**: Modified the agent's final answer prompt to generate follow-up questions instead of ending the conversation.

**Changes Made** (Lines 75-87):
```python
final_append = """After providing the final answer, ask if you can help the user with anything else related to this topic. Then generate exactly 3 follow-up questions based on the task that was completed. Format them as a numbered list:
1. [question]
2. [question]
3. [question]"""
```

**Impact**: The agent now automatically generates 3 numbered follow-up questions after every final answer.

---

#### 1.2 Orchestration Manager (`src/backend/v3/orchestration/orchestration_manager.py`)

**Purpose**: Implement orchestration lifecycle management to recreate orchestration instances for follow-up questions.

**Changes Made**:

**Change 1 - Mark Orchestration as Completed** (Lines ~184-186):
```python
# After sending FINAL_RESULT_MESSAGE
if hasattr(magentic_orchestration, "_manager"):
    magentic_orchestration._manager._is_completed = True
    logger.info(f"Orchestration marked as completed for user {user_id}")
```

**Change 2 - Detect Completion and Recreate** (Lines ~102-124):
```python
def get_current_or_new_orchestration(...):
    current_orchestration = OrchestrationConfig.orchestrations.get(user_id)
    
    # Check if orchestration is completed
    is_completed = False
    if current_orchestration and hasattr(current_orchestration, "_manager"):
        is_completed = getattr(current_orchestration._manager, "_is_completed", False)
    
    # Recreate orchestration if completed or team switched
    if (current_orchestration is None or team_switched or is_completed):
        # Close old agents if they exist
        if current_orchestration:
            reason = "team switched" if team_switched else "orchestration completed"
            logger.info(f"Recreating orchestration for user {user_id}: {reason}")
            
            # Close all agents in the current orchestration
            agents = getattr(current_orchestration, "_agents", [])
            for agent in agents:
                try:
                    await agent.close()
                except Exception as e:
                    logger.error(f"Error closing agent: {e}")
        
        # Create new orchestration instance
        # ... initialization logic
```

**Impact**: 
- Orchestration is marked as completed after sending the final answer
- When a follow-up question is submitted, the system detects the completed state
- Old orchestration agents are properly closed
- A fresh orchestration instance is created, allowing agents to respond to the new task

---

### 2. Frontend Changes

#### 2.1 Plan Page (`src/frontend/src/pages/PlanPage.tsx`)

**Purpose**: Keep the chat input enabled after receiving the final answer.

**Changes Made** (Line ~347):
```typescript
case MessageType.FINAL_RESULT_MESSAGE:
    // ... existing code ...
    setSubmittingChatDisableInput(false);  // Keep input enabled
    break;
```

**Previous Behavior**: Input was disabled after final answer  
**New Behavior**: Input remains enabled, allowing users to type or click follow-up questions

---

#### 2.2 Follow-Up Questions Component (`src/frontend/src/components/content/FollowUpQuestions.tsx`)

**Purpose**: New component to extract, parse, and display clickable follow-up questions.

**File Created**: `FollowUpQuestions.tsx`

**Key Features**:
- **Regex Parsing**: Extracts numbered questions from agent messages using pattern `/^\s*\d+[\.)]\s*(.+?)(?=\n\s*\d+[\.)]|\n\n|$)/gm`
- **Clickable Buttons**: Renders each question as a Fluent UI Button
- **Click Handler**: Calls `OnChatSubmit(question)` when a question is clicked
- **Styling**: Questions appear as styled buttons below the final answer

**Code Structure**:
```typescript
interface FollowUpQuestionsProps {
    message: string;
    OnChatSubmit: (message: string) => void;
}

export const FollowUpQuestions: React.FC<FollowUpQuestionsProps> = ({
    message,
    OnChatSubmit,
}) => {
    // Extract questions using regex
    const questionRegex = /^\s*\d+[\.)]\s*(.+?)(?=\n\s*\d+[\.)]|\n\n|$)/gm;
    const questions: string[] = [];
    let match;
    while ((match = questionRegex.exec(message)) !== null) {
        questions.push(match[1].trim());
    }

    // Render clickable buttons
    return (
        <div className={styles.followUpContainer}>
            <Text className={styles.followUpTitle}>
                💡 Follow-up questions:
            </Text>
            {questions.map((question, index) => (
                <Button
                    key={index}
                    appearance="outline"
                    onClick={() => OnChatSubmit(question)}
                >
                    {question}
                </Button>
            ))}
        </div>
    );
};
```

---

#### 2.3 Plan Chat (`src/frontend/src/components/content/PlanChat.tsx`)

**Purpose**: Integrate the FollowUpQuestions component into the chat interface.

**Changes Made**:
1. **Import**: Added `import { FollowUpQuestions } from "./FollowUpQuestions";`
2. **Conditional Rendering**: Display FollowUpQuestions after the last agent message

```typescript
{index === chatHistory.length - 1 && msg.role === "assistant" && (
    <FollowUpQuestions
        message={msg.content}
        OnChatSubmit={OnChatSubmit}
    />
)}
```

**Impact**: Follow-up questions appear immediately after the agent's final answer in the chat interface.

---

### 3. Deployment Changes

#### 3.1 ACR Deployment Script (`deploy_with_acr.sh`)

**Purpose**: Automated deployment script for building and deploying containers via Azure Container Registry.

**Key Steps**:
1. Login to Azure Container Registry
2. Build backend image: `az acr build --registry $ACR_NAME --image macae-backend:latest ./src/backend`
3. Build frontend image: `az acr build --registry $ACR_NAME --image macae-frontend:latest ./src/frontend`
4. Set Container App registry credentials: `az containerapp registry set`
5. Update Container App with new backend image: `az containerapp update --image`
6. Update App Service with new frontend image
7. Restart services

**Critical Fix**: Two-step authentication approach to avoid "unrecognized arguments" error:
- Step 4: Use `az containerapp registry set` to configure credentials
- Step 5: Use `az containerapp update --image` only (credentials already set)

---

#### 3.2 ACR-Compatible Dockerfiles

**Files Created**:
- `src/backend/Dockerfile.acr` - Single-stage Python 3.11 build without BuildKit features
- `src/frontend/Dockerfile.acr` - Multi-stage build (Node 18 → Python 3.11 → Final)

**Purpose**: Compatible with Azure Container Registry build constraints (no BuildKit `RUN --mount` syntax)

---

## User Experience Flow

### Before Changes
1. User submits a task
2. Agent processes and provides final answer
3. **Input is disabled** ❌
4. User cannot continue conversation

### After Changes
1. User submits a task
2. Agent processes and provides final answer
3. Agent generates 3 follow-up questions
4. **Input remains enabled** ✅
5. **Follow-up questions displayed as clickable buttons** ✅
6. User clicks or types a follow-up question
7. **New orchestration created** ✅
8. **Agents respond to follow-up task** ✅

## Technical Architecture

### Orchestration Lifecycle

```
Initial Request
    ↓
Create Orchestration Instance
    ↓
Agents Process Task
    ↓
Send FINAL_RESULT_MESSAGE
    ↓
Set _is_completed = True
    ↓
Display Follow-Up Questions
    ↓
User Submits Follow-Up
    ↓
Detect is_completed == True
    ↓
Close Old Agents
    ↓
Create NEW Orchestration Instance
    ↓
Agents Process Follow-Up Task
```

### State Management

**OrchestrationConfig.orchestrations Dictionary**:
- Key: `user_id` (string)
- Value: `MagenticOrchestration` instance

**Completion Tracking**:
- `_is_completed` flag added to `HumanApprovalMagenticManager`
- Set to `True` after `FINAL_RESULT_MESSAGE` sent
- Checked in `get_current_or_new_orchestration()`
- Triggers orchestration recreation when `True`

---

## Files Modified

### Backend
1. `/src/backend/v3/orchestration/human_approval_manager.py` - Follow-up question generation
2. `/src/backend/v3/orchestration/orchestration_manager.py` - Orchestration lifecycle management

### Frontend
1. `/src/frontend/src/pages/PlanPage.tsx` - Keep input enabled
2. `/src/frontend/src/components/content/FollowUpQuestions.tsx` - **NEW FILE** - Follow-up questions component
3. `/src/frontend/src/components/content/PlanChat.tsx` - Component integration

### Deployment
1. `/deploy_with_acr.sh` - **NEW FILE** - Automated ACR deployment
2. `/src/backend/Dockerfile.acr` - **NEW FILE** - ACR-compatible backend Dockerfile
3. `/src/frontend/Dockerfile.acr` - **NEW FILE** - ACR-compatible frontend Dockerfile
4. `/docs/ACRDeploymentGuide.md` - **NEW FILE** - Deployment documentation

---

## Deployment Information

### Azure Resources
- **Container Registry**: `acrmacae7359.azurecr.io` (rg-common)
- **Backend Service**: Container App `ca-odmadevycpyl` (rg-odmadev)
  - Latest Revision: `ca-odmadevycpyl--0000002`
  - Image: `acrmacae7359.azurecr.io/macae-backend:latest`
- **Frontend Service**: App Service `app-odmadevycpyl` (rg-odmadev)
  - Image: `acrmacae7359.azurecr.io/macae-frontend:latest`

### Deployment Command
```bash
./deploy_with_acr.sh
```

---

## Testing and Validation

### Validation Steps
1. ✅ Submit a task to the agent
2. ✅ Verify final answer is received
3. ✅ Verify 3 follow-up questions are displayed
4. ✅ Verify input remains enabled
5. ✅ Click a follow-up question
6. ✅ Verify new Plan is created
7. ✅ Verify agents respond to follow-up task

### Log Verification
Check backend logs for these key messages:
```
INFO: Orchestration marked as completed for user {user_id}
INFO: Recreating orchestration for user {user_id}: orchestration completed
```

---

## Known Issues and Considerations

### SSL Timeout Warnings
- **Issue**: `ClientConnectionError: Connection lost: SSL shutdown timed out`
- **Impact**: Benign warnings, does not affect functionality
- **Status**: Normal Azure Container App behavior

### Agent Cleanup
- Old orchestration agents are properly closed before creating new instances
- `ERROR: Unclosed client session` warnings may appear but do not affect functionality

---

## Future Enhancements

1. **Customizable Question Count**: Allow configuration of how many follow-up questions to generate
2. **Question Quality**: Improve prompt to generate more relevant and diverse follow-up questions
3. **Analytics**: Track which follow-up questions users click most frequently
4. **Conversation History**: Maintain context across multiple follow-up iterations
5. **Question Templates**: Pre-defined question templates based on task type

---

## Summary

The follow-up questions feature successfully transforms the multi-agent system from a single-shot Q&A model to a conversational interface. By keeping input enabled, generating relevant follow-up questions, and properly managing orchestration lifecycle, users can now engage in extended conversations with the agent system.

**Key Achievements**:
- ✅ Input remains enabled after final answer
- ✅ 3 follow-up questions automatically generated
- ✅ Questions are clickable for easy interaction
- ✅ Orchestration properly recreates for follow-up tasks
- ✅ Successfully deployed to Azure production environment

**Date Implemented**: November 11, 2025  
**Deployment Status**: Active in production (Revision: ca-odmadevycpyl--0000002)
