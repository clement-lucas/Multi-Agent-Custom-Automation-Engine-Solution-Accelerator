# Follow-Up Question Context Preservation

## Overview

This document describes the implementation of context preservation for follow-up questions in the Multi-Agent Custom Automation Engine. Previously, follow-up questions would create entirely new plans with new contexts. Now, follow-up questions continue the same plan while maintaining the full conversation history.

## Problem Statement

**Before:**
- User completes a task and receives follow-up questions
- Clicking a follow-up question or typing in chat creates a **NEW plan** with a **NEW context**
- AI agents don't see previous conversation
- User loses continuity between related questions
- Navigation to new plan_id breaks UX flow

**After:**
- User completes a task and receives follow-up questions
- Clicking a follow-up question or typing in chat **continues the SAME plan**
- AI agents maintain **full conversation context**
- User maintains continuity across multiple follow-ups
- No navigation away from current plan page

## Architecture Changes

### Backend Changes

#### 1. New API Endpoint: `/api/v3/continue_plan`

**File:** `src/backend/v3/api/router.py`

Added a new endpoint that continues an existing plan with a follow-up question:

```python
@app_v3.post("/continue_plan")
async def continue_plan(
    background_tasks: BackgroundTasks,
    request_body: dict,
    request: Request
)
```

**Request Body:**
```json
{
  "plan_id": "uuid-of-existing-plan",
  "follow_up_question": "The follow-up question text"
}
```

**Response:**
```json
{
  "status": "Plan continuation started successfully",
  "plan_id": "same-uuid",
  "session_id": "session-id"
}
```

**Key Features:**
- Validates follow-up question with RAI (Responsible AI) check
- Retrieves existing plan from database
- Updates plan status back to `IN_PROGRESS`
- Launches orchestration continuation as background task
- Returns same plan_id (not a new one)

#### 2. Orchestration Manager Enhancement

**File:** `src/backend/v3/orchestration/orchestration_manager.py`

Added new method `continue_orchestration()` to handle follow-up questions with context:

```python
async def continue_orchestration(self, user_id, plan_id, input_task) -> None:
    """Continue an existing orchestration with a follow-up question, maintaining context."""
```

**Key Features:**
- Gets existing orchestration instance for user (maintains context)
- Sets continuation flag on manager: `is_continuation = True`
- Stores current plan_id in manager for reference
- Prefixes follow-up with "Follow-up question: " for context clarity
- Invokes orchestration with follow-up while preserving conversation history
- Sends result via WebSocket to update UI
- Resets continuation flag after completion

#### 3. Human Approval Manager Enhancement

**File:** `src/backend/v3/orchestration/human_approval_manager.py`

Added fields to track continuation state:

```python
is_continuation: bool = False
current_plan_id: Optional[str] = None
```

Modified `final_append()` method to skip follow-up question generation during continuations:

```python
def final_append(self, final_answer: str, plan_id: str = None):
    """Only adds follow-up questions on initial completion, not on continuations."""
    if getattr(self, 'is_continuation', False):
        return final_answer  # Skip follow-up questions for continuations
    
    # Add follow-up questions for initial completion
    return final_answer + follow_up_prompt
```

**Rationale:** When continuing a conversation, we don't want to keep regenerating follow-up questions after every response. The user is already in a follow-up conversation flow.

### Frontend Changes

#### 1. Task Service Enhancement

**File:** `src/frontend/src/services/TaskService.tsx`

Added new method `continuePlan()`:

```typescript
static async continuePlan(
    planId: string,
    followUpQuestion: string
): Promise<{status: string; plan_id: string; session_id: string}> {
    const response = await apiService.post<{status: string; plan_id: string; session_id: string}>(
        '/api/v3/continue_plan',
        {
            plan_id: planId,
            follow_up_question: followUpQuestion
        }
    );
    return response;
}
```

#### 2. Plan Page Enhancement

**File:** `src/frontend/src/pages/PlanPage.tsx`

**Changed `handleFollowUpQuestion()`:**

Before:
```typescript
// Created NEW plan
const response = await TaskService.createPlan(question);
navigate(`/plan/${response.plan_id}`);  // Navigated away
```

After:
```typescript
// Continues SAME plan
const response = await TaskService.continuePlan(
    planData?.plan?.id || "",
    question
);
// Stays on same page, updates UI state
setSubmittingChatDisableInput(true);
setShowProcessingPlanSpinner(true);
await loadPlanData();  // Reload to get updated status
```

**Changed `handleOnchatSubmit()`:**

Before (when plan completed):
```typescript
const response = await TaskService.createPlan(chatInput);
navigate(`/plan/${response.plan_id}`);  // Created NEW plan
```

After (when plan completed):
```typescript
const response = await TaskService.continuePlan(
    planData.plan.id,
    chatInput
);
// Continues SAME plan with context
await loadPlanData();
```

## How Context is Preserved

### 1. Orchestration Instance Reuse

The system maintains one `MagenticOrchestration` instance per user (stored in `orchestration_config.orchestrations[user_id]`). This instance is reused across multiple tasks, which helps maintain:
- Agent state
- Runtime context
- Manager state

### 2. Conversation History in Manager

The `HumanApprovalMagenticManager` maintains conversation context across invocations because:
- Same manager instance is reused
- Manager has access to previous plan state
- Continuation flag signals to maintain context

### 3. Follow-Up Prefix

Follow-up questions are prefixed with "Follow-up question: " which:
- Signals to agents that this is a continuation
- Provides context that previous conversation exists
- Helps agents understand user intent better

## User Experience Flow

### Scenario: User Asks Follow-Up Question

1. **User completes initial task**
   - Plan status: `COMPLETED`
   - 3 AI-generated follow-up questions displayed

2. **User clicks follow-up button or types in chat**
   - Frontend calls `TaskService.continuePlan(plan_id, question)`
   - Backend endpoint `/api/v3/continue_plan` receives request

3. **Backend processes continuation**
   - Retrieves existing plan from database
   - Updates plan status to `IN_PROGRESS`
   - Calls `OrchestrationManager.continue_orchestration()`
   - Sets `is_continuation = True` on manager

4. **Orchestration continues with context**
   - Gets existing orchestration instance (preserves context)
   - Invokes with follow-up question prefixed
   - Agents see full conversation context
   - Generates response considering previous interaction

5. **Result sent to frontend**
   - WebSocket sends `FINAL_RESULT_MESSAGE`
   - Frontend displays new response in same plan page
   - Plan status updates to `COMPLETED` again
   - New follow-up questions can be asked

## Benefits

1. **Continuity:** Users can have natural multi-turn conversations without losing context
2. **Better AI Responses:** Agents provide more relevant answers with full conversation history
3. **Improved UX:** No jarring navigation between plans
4. **Efficiency:** Single plan tracks entire conversation thread
5. **Scalability:** Same orchestration instance handles multiple follow-ups

## Limitations and Considerations

1. **Context Window:** Very long conversations may eventually hit model context limits
2. **State Management:** Orchestration instance is kept alive per user (memory consideration)
3. **Follow-Up Generation:** Currently disabled during continuations to avoid repetition
4. **Session Management:** All follow-ups share same session_id as original plan

## Testing Recommendations

1. **Single Follow-Up Test:**
   - Complete a task
   - Ask one follow-up question
   - Verify agent references previous conversation

2. **Multi-Turn Conversation Test:**
   - Complete a task
   - Ask first follow-up
   - After completion, ask another follow-up
   - Verify full conversation context maintained

3. **Context Verification Test:**
   - Ask about specific detail in initial task
   - In follow-up, ask "what about that [detail]?"
   - Verify agent understands reference

4. **Navigation Test:**
   - Ensure page doesn't reload/navigate
   - Verify UI updates correctly
   - Check WebSocket messages received

5. **Error Handling Test:**
   - Test with invalid plan_id
   - Test with RAI-blocked content
   - Verify error messages displayed

## Future Enhancements

1. **Conversation History Visualization:** Show conversation thread in UI
2. **Context Pruning:** Intelligently summarize old context to manage token limits
3. **Branching Conversations:** Allow multiple follow-up threads from same initial task
4. **Context Export:** Enable downloading conversation history
5. **Smart Follow-Up Generation:** Generate follow-ups that consider conversation history

## API Reference

### POST /api/v3/continue_plan

**Description:** Continue an existing plan with a follow-up question while maintaining conversation context.

**Request Headers:**
- `user_principal_id`: User ID from authentication

**Request Body:**
```json
{
  "plan_id": "string (required)",
  "follow_up_question": "string (required)"
}
```

**Response (200 OK):**
```json
{
  "status": "Plan continuation started successfully",
  "plan_id": "string",
  "session_id": "string"
}
```

**Error Responses:**
- `400 Bad Request`: Missing required fields or RAI check failed
- `404 Not Found`: Plan not found
- `500 Internal Server Error`: Orchestration continuation failed

## Related Documentation

- [Follow-Up Questions Feature](./follow_up_questions_feature.md) - Original feature documentation
- [Follow-Up Questions Feature (Japanese)](./follow_up_questions_feature.ja.md) - Japanese translation
- [Architecture Diagrams](./follow_up_questions_feature.md#technical-architecture-diagrams) - System flow diagrams
