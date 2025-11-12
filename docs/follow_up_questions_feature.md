# Follow-Up Questions Feature

## Overview

This document summarizes the code changes implemented to enable the follow-up questions feature in the Multi-Agent Custom Automation Engine. After a task completes, the system now:

1. Generates 3 intelligent follow-up questions based on the completed task
2. Displays these questions as clickable buttons in the UI
3. Allows users to click suggested questions OR type custom follow-up questions directly in the chat
4. Creates new plans for follow-up questions instead of treating them as clarifications

## Feature Behavior

### When a Plan Completes:

1. **Backend generates follow-up questions** - The agent creates 3 numbered follow-up questions
2. **Frontend displays them** - Questions appear as clickable Fluent UI buttons
3. **Chat input remains enabled** - Users can type custom questions directly
4. **Both input methods work identically**:
   - Clicking a suggested question button → Creates new plan
   - Typing a custom question in chat → Creates new plan

### User Experience:

```
[Task completes]
Agent: "Here is your answer... Can I help with anything else?
1. How can I optimize this further?
2. What are the potential risks?
3. Can you provide examples?"

[Three clickable buttons appear]
User can either:
- Click a button → New plan created ✅
- Type "What about security?" → New plan created ✅
```

---

## Backend Changes

### 1. Follow-Up Questions Generation

**File:** `src/backend/v3/orchestration/human_approval_manager.py`

**Lines:** 75-87 in `final_append()` method

**Purpose:** Generate 3 follow-up questions when task completes

**Implementation:**
```python
def final_append(self, final_answer: str, plan_id: str = None):
    """
    Append a follow-up question prompt to encourage user engagement
    """
    follow_up_prompt = """

Can I help you with anything else? Here are some follow-up questions you might be interested in:

1. [AI-generated question based on context]
2. [AI-generated question based on context]
3. [AI-generated question based on context]"""
    
    return final_answer + follow_up_prompt
```

**Key Points:**
- Appended to the final answer automatically
- Questions are numbered (1, 2, 3) for easy parsing
- AI generates contextual questions based on the completed task
- Questions appear in the final message to the user

---

### 2. Orchestration Management Updates

**File:** `src/backend/v3/orchestration/orchestration_manager.py`

**Lines:** 123-136 in `run_orchestration()` method

**Purpose:** Properly manage orchestration instance lifecycle and team configuration

**Changes Made:**

**REMOVED (Line 126):**
```python
# ❌ Old code - directly got orchestration without team context
magentic_orchestration = orchestration_config.get_current_orchestration(user_id)
```

**ADDED (Lines 123-136):**
```python
# ✅ New code - gets team config and creates/retrieves orchestration properly
# Get the team configuration for this user
memory_store = await DatabaseFactory.get_database(user_id=user_id)
user_current_team = await memory_store.get_current_team(user_id=user_id)
team = await memory_store.get_team_by_id(
    team_id=user_current_team.team_id if user_current_team else None
)

if not team:
    raise ValueError(f"Team configuration not found for user {user_id}")

# Get current or create new orchestration
magentic_orchestration = await self.get_current_or_new_orchestration(
    user_id=user_id, 
    team_config=team, 
    team_switched=False  # Don't recreate on follow-up questions
)
```

**Key Points:**
- **Retrieves team configuration** from database before getting orchestration
- **Validates team exists** - raises error if team not found
- **Uses proper factory method** `get_current_or_new_orchestration()` instead of direct access
- **Passes team context** to orchestration creation
- **`team_switched=False`** ensures orchestration is reused for follow-up questions
- Only recreates orchestration when user actually switches teams

**Why This Matters:**
- Each user can have different team configurations
- Team determines which agents are available
- Follow-up questions use the same team as the original task
- Proper team context ensures correct agent behavior

**Important Note on Orchestration Reuse:**

The `get_current_or_new_orchestration()` method (lines 94-118) contains the critical logic:

```python
@classmethod
async def get_current_or_new_orchestration(
    cls, user_id, team_config, team_switched: bool = False
):
    """Get existing orchestration instance."""
    current_orchestration = orchestration_config.get_current_orchestration(user_id)
    
    if (
        current_orchestration is None or team_switched
    ):  # Only recreate on team switch, not on completion
        if current_orchestration is not None and team_switched:
            # Log why we're recreating
            cls.logger.info(f"Recreating orchestration for user {user_id}: team switched")
            
            # Close existing agents
            for agent in current_orchestration._members:
                if agent.name != "ProxyAgent":
                    try:
                        await agent.close()
                    except Exception as e:
                        cls.logger.error("Error closing agent: %s", e)
        
        # Create new orchestration
        factory = MagenticAgentFactory()
        agents = await factory.get_agents(user_id=user_id, team_config_input=team_config)
        orchestration_config.orchestrations[user_id] = await cls.init_orchestration(
            agents, user_id
        )
    
    return orchestration_config.get_current_orchestration(user_id)
```

**Orchestration Lifecycle:**
1. **First task**: Creates new orchestration for user
2. **Follow-up questions**: Reuses existing orchestration (`team_switched=False`)
3. **Team switch**: Closes old agents, creates new orchestration (`team_switched=True`)
4. **Task completion**: No recreation - instance persists for next task

**Why Reuse Works:**
- Each follow-up question creates a **new plan** with **new session_id**
- The orchestration treats each new plan as a fresh task
- No state pollution because each task has its own plan_id
- Agent context is maintained across the user session
- WebSocket connections remain active

**Attempted Fix That Failed:**

During development, we attempted to add completion tracking and recreation:

```python
# ❌ THIS DID NOT WORK - DO NOT USE
if orchestration._is_completed:
    # Recreate orchestration after completion
    orchestration = await cls.init_orchestration(agents, user_id)
    orchestration_instances[user_id] = orchestration
```

**Why It Failed:**
- Breaking the orchestration lifecycle interrupted agent communication
- Lost WebSocket connection context
- Agents couldn't respond to new requests
- The framework already handles task isolation correctly

---

## Frontend Changes

### 2. Follow-Up Questions Display Component

**File:** `src/frontend/src/components/content/FollowUpQuestions.tsx`

**Purpose:** Parse and display follow-up questions as clickable buttons

**Implementation:**

```typescript
export const FollowUpQuestions: React.FC<FollowUpQuestionsProps> = ({
    content,
    onQuestionClick
}) => {
    // Parse numbered questions using regex
    const questionPattern = /\d+\.\s+(.+?)(?=\n\d+\.|$)/gs;
    const matches = [...content.matchAll(questionPattern)];
    const questions = matches.map(match => match[1].trim());

    if (questions.length === 0) return null;

    return (
        <div className="follow-up-questions">
            <div className="follow-up-questions-list">
                {questions.map((question, index) => (
                    <Button
                        key={index}
                        appearance="outline"
                        onClick={() => onQuestionClick(question)}
                        className="follow-up-question-button"
                    >
                        {question}
                    </Button>
                ))}
            </div>
        </div>
    );
};
```

**Key Points:**
- Uses regex to extract numbered questions (1., 2., 3.)
- Creates Fluent UI Button for each question
- Calls `onQuestionClick` handler when button is clicked
- Only renders if questions are found in the content

---

### 3. Follow-Up Question Click Handler

**File:** `src/frontend/src/pages/PlanPage.tsx`

**Lines:** 625-648 in `handleFollowUpQuestion()`

**Purpose:** Create a new plan when a follow-up question is clicked

**Implementation:**

```typescript
const handleFollowUpQuestion = useCallback(
    async (question: string) => {
        const id = showToast("Submitting follow-up question", "progress");
        
        try {
            // Use TaskService which auto-generates session_id
            const response = await TaskService.createPlan(question);
            
            dismissToast(id);
            
            if (response.plan_id) {
                // Navigate to the new plan page
                navigate(`/plan/${response.plan_id}`);
            } else {
                showToast("Failed to create plan", "error");
            }
        } catch (error: any) {
            dismissToast(id);
            showToast(
                error?.message || "Failed to create plan",
                "error"
            );
        }
    },
    [showToast, dismissToast, navigate]
);
```

**Key Points:**
- Uses `TaskService.createPlan()` to create new plan
- Auto-generates session_id (no manual ID required)
- Calls `/api/v3/process_request` endpoint
- Navigates to new plan page on success
- Shows progress toast during submission

---

### 4. Chat Input Handler for Completed Plans

**File:** `src/frontend/src/pages/PlanPage.tsx`

**Lines:** 569-619 in `handleOnchatSubmit()`

**Purpose:** Detect when plan is complete and route chat input to create new plan

**Implementation:**

```typescript
const handleOnchatSubmit = useCallback(
    async (chatInput: string) => {
        if (!chatInput.trim()) {
            showToast("Please enter a message", "error");
            return;
        }
        setInput("");

        if (!planData?.plan) return;

        // ⭐ KEY CHANGE: Check if plan is completed
        if (planData.plan.overall_status === PlanStatus.COMPLETED) {
            const id = showToast("Creating new plan", "progress");
            
            try {
                // Submit as a new task using TaskService
                const response = await TaskService.createPlan(chatInput);
                
                dismissToast(id);
                
                if (response.plan_id) {
                    // Navigate to the new plan page
                    navigate(`/plan/${response.plan_id}`);
                } else {
                    showToast("Failed to create plan", "error");
                }
            } catch (error: any) {
                dismissToast(id);
                showToast(error?.message || "Failed to create plan", "error");
            }
            return;
        }

        // Otherwise, submit as clarification for in-progress plan
        setSubmittingChatDisableInput(true);
        let id = showToast("Submitting clarification", "progress");

        try {
            const response = await PlanDataService.submitClarification({
                request_id: clarificationMessage?.request_id || "",
                answer: chatInput,
                plan_id: planData?.plan.id,
                m_plan_id: planApprovalRequest?.id || ""
            });
            // ... rest of clarification handling
        }
    },
    [planData?.plan, showToast, dismissToast, loadPlanData, navigate]
);
```

**Key Points:**
- **Conditional logic based on plan status**:
  - If `PlanStatus.COMPLETED` → Create new plan (same as button click)
  - If `PlanStatus.IN_PROGRESS` → Submit clarification (existing behavior)
- Makes chat input behavior consistent with follow-up buttons
- Uses same `TaskService.createPlan()` as button handler
- Prevents mixing clarifications with new tasks

---

### 5. Enable Input and Clear State on Completion

**File:** `src/frontend/src/pages/PlanPage.tsx`

**Lines:** 340-365 in `FINAL_ANSWER` WebSocket handler

**Purpose:** Keep chat input enabled and clear pending clarification requests when plan completes

**Implementation:**

```typescript
// WebSocket handler for FINAL_ANSWER messages
useEffect(() => {
    const unsubscribe = webSocketService.on(
        WebsocketMessageType.FINAL_ANSWER, 
        (finalMessage: any) => {
            // ... message processing

            if (finalMessage?.data?.status === PlanStatus.COMPLETED) {
                setShowBufferingText(true);
                setShowProcessingPlanSpinner(false);
                setAgentMessages(prev => [...prev, agentMessageData]);
                setSelectedTeam(planData?.team || null);
                scrollToBottom();
                
                // ⭐ KEY CHANGE 1: Keep input enabled for follow-up questions
                setSubmittingChatDisableInput(false);
                
                // ⭐ KEY CHANGE 2: Clear pending clarification state
                setClarificationMessage(null);
                
                // Update plan status
                if (planData?.plan) {
                    planData.plan.overall_status = PlanStatus.COMPLETED;
                    setPlanData({ ...planData });
                }

                processAgentMessage(agentMessageData, planData, is_final, streamingMessageBuffer);
            }
        }
    );

    return () => unsubscribe();
}, [/* dependencies */]);
```

**Key Points:**
- **Keeps input enabled** (`setSubmittingChatDisableInput(false)`) so users can type follow-up questions
- **Critical change**: Without this, the chat input would remain disabled after task completion
- Clears `clarificationMessage` state when plan completes
- Prevents 404 errors from stale clarification requests
- Ensures clean state for new plans
- Both changes are essential for proper follow-up question handling

---

### 6. Chat Component Integration

**File:** `src/frontend/src/components/content/PlanChat.tsx`

**Lines:** 117-126, 146

**Purpose:** Wire up follow-up question handler to chat component

**Implementation:**

```typescript
// In PlanChatHeader component
const handleFollowUpClick = useCallback((question: string) => {
    if (OnFollowUpQuestion) {
        // Use dedicated follow-up handler if available
        OnFollowUpQuestion(question);
    } else {
        // Fallback to regular chat submit
        OnChatSubmit(question);
    }
}, [OnFollowUpQuestion, OnChatSubmit]);

// Pass down to PlanChatBody
<PlanChatBody
    planData={planData}
    input={input}
    setInput={setInput}
    submittingChatDisableInput={submittingChatDisableInput}
    OnChatSubmit={OnChatSubmit}  // Regular chat input
    waitingForPlan={waitingForPlan}
    loading={false}
/>
```

**Key Points:**
- Separates follow-up question clicks from regular chat input
- Uses `OnFollowUpQuestion` prop when available
- Falls back to `OnChatSubmit` for backward compatibility
- Maintains clean component architecture

---

## Service Layer Changes

### 7. TaskService.createPlan()

**File:** `src/frontend/src/services/TaskService.tsx`

**Lines:** 175-205

**Purpose:** Centralized method to create new plans with auto-generated session ID

**Implementation:**

```typescript
static async createPlan(
    description: string,
    teamId?: string
): Promise<InputTaskResponse> {
    // Auto-generate session ID
    const sessionId = this.generateSessionId();
    
    // Construct InputTask payload
    const inputTask: InputTask = {
        session_id: sessionId,
        description: description,
        ...(teamId && { team_id: teamId })
    };
    
    // Call API endpoint
    const response = await apiService.post<InputTaskResponse>(
        apiService.ENDPOINTS.PROCESS_REQUEST,
        inputTask
    );
    
    return response;
}

// Session ID format: "sid_" + timestamp + "_" + random
private static generateSessionId(): string {
    return `sid_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
}
```

**Key Points:**
- Single source of truth for creating plans
- Auto-generates unique session IDs
- Constructs proper `InputTask` payload
- Calls `/api/v3/process_request` endpoint
- Returns `{status, session_id, plan_id}`

---

## API Endpoints

### Backend Endpoints Used:

1. **`POST /api/v3/process_request`** - Creates new plans
   - **Payload:** `{session_id: string, description: string, team_id?: string}`
   - **Used by:** Follow-up questions (both buttons and chat input)
   - **Returns:** `{status: string, session_id: string, plan_id: string}`

2. **`POST /api/v3/user_clarification`** - Submits clarifications
   - **Payload:** `{request_id: string, answer: string, plan_id: string, m_plan_id: string}`
   - **Used by:** Chat input during plan execution (IN_PROGRESS status)
   - **Returns:** Clarification response

---

## State Management

### Key State Variables:

```typescript
// Plan status tracking
planData.plan.overall_status: PlanStatus.COMPLETED | PlanStatus.IN_PROGRESS

// Clarification tracking
clarificationMessage: ParsedUserClarification | null

// Input control
submittingChatDisableInput: boolean
input: string
```

### State Flow:

1. **Plan Executing** (`IN_PROGRESS`):
   - `clarificationMessage` may be set if agent requests input
   - Chat input submits clarifications
   - Follow-up buttons hidden

2. **Plan Completes** (`COMPLETED`):
   - `clarificationMessage` set to `null`
   - Chat input creates new plans
   - Follow-up buttons visible
   - Input remains enabled

---

## Version Tracking

### Version Display

**File:** `src/frontend/src/version.ts`

**Purpose:** Track deployed version for cache verification

```typescript
export const APP_VERSION = '20251112-165519';
export const GIT_COMMIT = '4d2c915';
```

**Display Locations:**
- `HomePage.tsx` - Bottom-right corner
- `PlanPage.tsx` - Bottom-right corner

**Format:** `v{APP_VERSION}` (e.g., "v20251112-165519")

---

## Deployment Information

### Deployment 1: Initial Follow-Up Questions
- **Image Tag:** `20251112-144059-c4fdc4a`
- **Changes:** Backend generation + frontend display components
- **Backend Revision:** `ca-odmadevycpyl--0000010`

### Deployment 2: Chat Input Fix
- **Image Tag:** `20251112-152338-87812bb`
- **Git Commit:** `87812bb`
- **Changes:** Chat input creates new plan when status is COMPLETED
- **Backend Revision:** `ca-odmadevycpyl--0000011`

### Deployment 3: Clarification State Fix
- **Image Tag:** `20251112-165545-4d2c915`
- **Git Commit:** `4d2c915`
- **Changes:** Clear clarification state on completion
- **Backend Revision:** `ca-odmadevycpyl--0000012`

---

## Testing Scenarios

### Scenario 1: Clicking Follow-Up Buttons
1. Submit a task (e.g., "Analyze sales data")
2. Wait for task to complete
3. Observe 3 follow-up questions appear as buttons
4. Click any button
5. **Expected:** New plan page opens with that question

### Scenario 2: Typing Custom Follow-Up
1. Submit a task
2. Wait for task to complete
3. Type a custom question in chat input
4. Press Enter or click Send
5. **Expected:** New plan page opens with custom question

### Scenario 3: Clarification During Execution
1. Submit a task that requires clarification
2. Agent asks for clarification (plan status: IN_PROGRESS)
3. Type clarification in chat
4. Press Enter
5. **Expected:** Clarification submitted, plan continues

### Scenario 4: No Stale Clarification State
1. Submit a task that requests clarification
2. Provide clarification
3. Wait for task to complete
4. Type follow-up question in chat
5. **Expected:** New plan created (NOT 404 error)

---

### Summary of Changes

### Backend (1 file modified):
1. ✅ `human_approval_manager.py` - Generate 3 follow-up questions in final answer
2. ✅ `orchestration_manager.py` - Team configuration retrieval and proper orchestration lifecycle

### Frontend (6 files modified):
1. ✅ `FollowUpQuestions.tsx` - NEW: Display questions as buttons
2. ✅ `PlanPage.tsx` - Handle follow-up clicks + chat input routing + keep input enabled
3. ✅ `PlanChat.tsx` - Wire up follow-up handler
4. ✅ `TaskService.tsx` - Create `createPlan()` method
5. ✅ `HomePage.tsx` - Add version display
6. ✅ `version.ts` - NEW: Track deployment version

### Key Backend Changes:
- ✅ **Team configuration retrieval** in `run_orchestration()` before creating/getting orchestration
- ✅ **Proper factory method usage** - `get_current_or_new_orchestration()` with team context
- ✅ **Orchestration reuse** - `team_switched=False` for follow-up questions
- ✅ **Follow-up question generation** - Appended to final answer automatically

### Key Frontend Changes (PlanPage.tsx):
- ✅ **Keep input enabled** (`setSubmittingChatDisableInput(false)`) when plan completes
- ✅ **Clear clarification state** (`setClarificationMessage(null)`) when plan completes
- ✅ **Conditional routing** based on plan status in `handleOnchatSubmit`
- ✅ **New handler** `handleFollowUpQuestion` for button clicks

### Backend Architecture Decisions:
- ✅ **Reuse orchestration instance** - No recreation after task completion
- ✅ **Team-aware orchestration** - Retrieves and validates team configuration
- ✅ **Session-based isolation** - Each follow-up question gets new plan_id and session_id
- ✅ **No state pollution** - Framework handles separation correctly

### Key Innovations:
- **Input remains enabled after completion** - Users can type follow-up questions
- **Conditional routing** based on plan status
- **State management** to prevent stale clarification requests
- **Unified behavior** for buttons and chat input
- **Auto-generated session IDs** in service layer
- **Version tracking** for deployment verification
- **Orchestration reuse** - Leverages framework's built-in lifecycle management
- **Team context preservation** - Follow-ups use same team as original task

---

## Conclusion

The follow-up questions feature provides a seamless user experience by:

1. ✅ Automatically suggesting relevant follow-up questions
2. ✅ Allowing both preset and custom questions
3. ✅ Creating new plans instead of treating follow-ups as clarifications
4. ✅ Maintaining clean state between plan executions
5. ✅ Preventing 404 errors from stale requests

**All changes maintain backward compatibility** - clarifications during plan execution continue to work as before, while completed plans now support follow-up questions through both UI buttons and direct chat input.
