# フォローアップ質問機能

## 概要

このドキュメントは、マルチエージェントカスタム自動化エンジンにフォローアップ質問機能を実装するために行われたコード変更をまとめたものです。タスク完了後、システムは以下の動作を行います：

1. 完了したタスクに基づいて3つのインテリジェントなフォローアップ質問を生成
2. これらの質問をクリック可能なボタンとしてUIに表示
3. ユーザーが提案された質問をクリックするか、チャットに直接カスタムフォローアップ質問を入力できる
4. フォローアップ質問を明確化として扱うのではなく、新しいプランを作成

## 機能の動作

### プラン完了時：

1. **バックエンドがフォローアップ質問を生成** - エージェントが3つの番号付きフォローアップ質問を作成
2. **フロントエンドがそれらを表示** - 質問がクリック可能なFluent UIボタンとして表示される
3. **チャット入力は有効のまま** - ユーザーがカスタム質問を直接入力できる
4. **両方の入力方法が同じように動作**：
   - 提案された質問ボタンをクリック → 新しいプランを作成
   - チャットにカスタム質問を入力 → 新しいプランを作成

### ユーザーエクスペリエンス：

```
[タスク完了]
エージェント: "こちらが回答です... 他に何かお手伝いできることはありますか？
1. これをさらに最適化するにはどうすればよいですか？
2. 潜在的なリスクは何ですか？
3. 例を提供していただけますか？"

[3つのクリック可能なボタンが表示される]
ユーザーは以下のいずれかを選択できます：
- ボタンをクリック → 新しいプランが作成される ✅
- 「セキュリティについてはどうですか？」と入力 → 新しいプランが作成される ✅
```

---

## 技術アーキテクチャ

### フォローアップ質問を含むオーケストレーションライフサイクル

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         ユーザーが新しいタスクを開始                           │
│                    (初回またはフォローアップ質問)                              │
└────────────────────────────────┬────────────────────────────────────────────┘
                                 │
                                 ▼
                    ┌────────────────────────┐
                    │   フロントエンド (React)│
                    │  TaskService.createPlan│
                    └────────────┬───────────┘
                                 │
                                 │ POST /api/v3/process_request
                                 │ {session_id, description, team_id?}
                                 │
                                 ▼
┌────────────────────────────────────────────────────────────────────────────┐
│                        バックエンド オーケストレーションマネージャー             │
│                         (orchestration_manager.py)                           │
└────────────────────────────────┬───────────────────────────────────────────┘
                                 │
                                 ▼
                    ┌────────────────────────┐
                    │  run_orchestration()   │
                    │   行 123-136           │
                    └────────────┬───────────┘
                                 │
                                 │ 1. チーム構成を取得
                                 │    memory_store = DatabaseFactory.get_database(user_id)
                                 │    team = memory_store.get_team_by_id(...)
                                 │
                                 ▼
                    ┌────────────────────────┐
                    │ get_current_or_new     │
                    │    _orchestration()    │
                    │   行 94-118            │
                    └────────────┬───────────┘
                                 │
                    ┌────────────┴────────────┐
                    │                         │
        オーケストレーションは存在するか?   チームが切り替わったか?
                    │                         │
        ┌───────────▼─────────┐   ┌──────────▼───────────┐
        │   いいえ (初回タスク) │   │   はい (チーム変更)   │
        └─────────┬───────────┘   └──────────┬───────────┘
                  │                           │
                  │                           │ 古いエージェントを閉じる
                  │                           │ await agent.close()
                  │                           │
                  └───────────┬───────────────┘
                              │
                              ▼
                ┌─────────────────────────────┐
                │  新しいオーケストレーションを作成 │
                │  MagenticAgentFactory       │
                │  init_orchestration()       │
                └──────────────┬──────────────┘
                               │
                               │ orchestration_configに保存
                               │ orchestrations[user_id] = new_instance
                               │
        ┌──────────────────────┴──────────────────────┐
        │                                             │
        ▼                                             ▼
┌───────────────┐                          ┌─────────────────┐
│ はい (存在する) │                          │ オーケストレーション │
│ 再利用する     │                          │     作成完了     │
└───────┬───────┘                          └────────┬────────┘
        │                                           │
        │ 同じオーケストレーションインスタンス        │
        │ 異なるplan_id                             │
        │ 異なるsession_id                          │
        │                                           │
        └───────────────┬───────────────────────────┘
                        │
                        ▼
        ┌───────────────────────────────┐
        │   エージェントでタスクを実行    │
        │   (Semantic Kernel)           │
        │   - WebSocket接続             │
        │   - エージェントコンテキスト保持│
        │   - 新しいplan_idを作成        │
        └───────────────┬───────────────┘
                        │
                        │ タスク実行中...
                        │ エージェントが協力...
                        │
                        ▼
        ┌───────────────────────────────┐
        │    タスク完了                  │
        │   (PlanStatus.COMPLETED)      │
        └───────────────┬───────────────┘
                        │
                        ▼
        ┌───────────────────────────────┐
        │ human_approval_manager.py     │
        │   final_append()              │
        │   行 75-87                    │
        └───────────────┬───────────────┘
                        │
                        │ 3つのフォローアップ質問を生成
                        │ 最終回答に追加
                        │
                        ▼
        ┌───────────────────────────────┐
        │   WebSocket: FINAL_ANSWER     │
        │   {status: COMPLETED, ...}    │
        └───────────────┬───────────────┘
                        │
                        ▼
┌───────────────────────────────────────────────────────────────────────────┐
│                        フロントエンド (PlanPage.tsx)                        │
│                      WebSocketハンドラー 行 340-365                        │
└───────────────────────────────────────────────────────────────────────────┘
                        │
                        ├──► setSubmittingChatDisableInput(false)
                        │    (入力を有効に保つ)
                        │
                        ├──► setClarificationMessage(null)
                        │    (古い状態をクリア)
                        │
                        └──► フォローアップ質問を表示
                             (FollowUpQuestions.tsx)
                        │
        ┌───────────────┴───────────────┐
        │                               │
        ▼                               ▼
┌─────────────────┐          ┌──────────────────┐
│ ユーザーが      │          │ ユーザーが       │
│ フォローアップ  │          │ チャット入力に   │
│ ボタンをクリック│          │ テキストを入力   │
└────────┬────────┘          └────────┬─────────┘
         │                            │
         │ handleFollowUpQuestion     │ handleOnchatSubmit
         │ 行 625-648                 │ 行 569-619
         │                            │
         │                            │ チェック: planData.plan.overall_status
         │                            │
         │                            ├─► COMPLETED の場合:
         │                            │   TaskService.createPlan()
         │                            │
         │                            └─► IN_PROGRESS の場合:
         │                                submitClarification()
         │                            │
         └────────────┬───────────────┘
                      │
                      ▼
         ┌────────────────────────┐
         │ TaskService.createPlan │
         │   行 175-205           │
         └────────────┬───────────┘
                      │
                      │ 新しいsession_idを生成
                      │ sid_{timestamp}_{random}
                      │
                      ▼
         ┌────────────────────────┐
         │ 新しいプランに移動      │
         │ /plan/{new_plan_id}    │
         └────────────┬───────────┘
                      │
                      └──────► サイクル繰り返し
                              (オーケストレーションインスタンス再利用)
                              (新しいplan_id作成)
                              (同じエージェント、同じチーム)


═══════════════════════════════════════════════════════════════════════════
                           主要なアーキテクチャポイント
═══════════════════════════════════════════════════════════════════════════

1. オーケストレーションの再利用
   ✅ ユーザーごとに1つのオーケストレーションインスタンス
   ✅ 複数のタスク/フォローアップにわたって永続化
   ✅ チーム切り替え時のみ再作成
   ✅ 各タスクは新しいplan_idとsession_idを取得

2. チーム構成
   ✅ 各オーケストレーションリクエストでデータベースから取得
   ✅ オーケストレーション作成前に検証
   ✅ 利用可能なエージェントを決定
   ✅ フォローアップ質問用に保持 (team_switched=False)

3. 状態の分離
   ✅ 各タスク: 一意のplan_id + session_id
   ✅ タスク間で状態の汚染なし
   ✅ フレームワークが分離を正しく処理
   ✅ エージェントコンテキストはオーケストレーションインスタンスで保持

4. 入力ルーティング
   ✅ 完了したプラン: 新しいプランを作成
   ✅ 進行中のプラン: 明確化を送信
   ✅ ボタンとチャット入力の両方が同じように動作
   ✅ 完了時に明確化状態をクリア

5. WebSocket接続
   ✅ オーケストレーションの存続期間中維持
   ✅ エージェントがフロントエンドと通信可能
   ✅ フォローアップに再接続不要
   ✅ オーケストレーションが再作成されると失われる

═══════════════════════════════════════════════════════════════════════════
```

### 状態遷移図

```
                    ┌──────────────────┐
                    │   プランなし      │
                    │   (初期状態)      │
                    └────────┬─────────┘
                             │
                             │ ユーザーがタスクを送信
                             │ POST /process_request
                             │
                             ▼
                    ┌──────────────────┐
                    │   進行中         │◄──────┐
                    │   IN_PROGRESS    │       │
                    │  - 実行中        │       │ 明確化
                    │  - 明確化を      │       │ 送信済み
                    │    要求する可能性│       │
                    └────────┬─────────┘       │
                             │                 │
                             │ タスク完了      │
                             │                 │
                             ▼                 │
                    ┌──────────────────┐       │
                    │   完了           │       │
                    │   COMPLETED      │       │
                    │  ✅ 入力有効     │       │
                    │  ✅ フォローアップ│      │
                    │     表示         │       │
                    │  ✅ 明確化状態   │       │
                    │     クリア済み   │       │
                    └────────┬─────────┘       │
                             │                 │
              ┌──────────────┴──────────────┐  │
              │                             │  │
              ▼                             ▼  │
    ┌─────────────────┐          ┌─────────────────┐
    │ フォローアップ  │          │  チャットに入力  │
    │ クリック        │          │                 │
    └─────────┬───────┘          └────────┬────────┘
              │                           │
              │                           │ ステータスチェック:
              │                           │ COMPLETED?
              │                           │
              └───────────┬───────────────┘
                          │
                          │ はい: 新しいプランを作成
                          │ (両方のルートが同じ)
                          │
                          ▼
                    ┌──────────────────┐
                    │   新しいプラン    │
                    │   IN_PROGRESS    │
                    │                  │
                    │  - 新しいplan_id │
                    │  - 新しいsession_id│
                    │  - 同じチーム     │
                    │  - 再利用された   │
                    │    オーケストレーション│
                    └──────────────────┘
```

---

## バックエンドの変更

### 1. フォローアップ質問の生成

**ファイル:** `src/backend/v3/orchestration/human_approval_manager.py`

**行:** 75-87 `final_append()` メソッド内

**目的:** タスク完了時に3つのフォローアップ質問を生成

**実装:**
```python
def final_append(self, final_answer: str, plan_id: str = None):
    """
    ユーザーエンゲージメントを促すためのフォローアップ質問プロンプトを追加
    """
    follow_up_prompt = """

他に何かお手伝いできることはありますか？興味がありそうなフォローアップ質問をいくつかご紹介します：

1. [コンテキストに基づくAI生成質問]
2. [コンテキストに基づくAI生成質問]
3. [コンテキストに基づくAI生成質問]"""
    
    return final_answer + follow_up_prompt
```

**主要ポイント:**
- 最終回答に自動的に追加
- 質問は番号付き (1, 2, 3) で簡単に解析可能
- AIが完了したタスクに基づいてコンテキストに応じた質問を生成
- 質問はユーザーへの最終メッセージに表示

---

### 2. オーケストレーション管理の更新

**ファイル:** `src/backend/v3/orchestration/orchestration_manager.py`

**行:** 123-136 `run_orchestration()` メソッド内

**目的:** オーケストレーションインスタンスのライフサイクルとチーム構成を適切に管理

**変更内容:**

**削除 (行 126):**
```python
# ❌ 古いコード - チームコンテキストなしでオーケストレーションを直接取得
magentic_orchestration = orchestration_config.get_current_orchestration(user_id)
```

**追加 (行 123-136):**
```python
# ✅ 新しいコード - チーム構成を取得してオーケストレーションを適切に作成/取得
# このユーザーのチーム構成を取得
memory_store = await DatabaseFactory.get_database(user_id=user_id)
user_current_team = await memory_store.get_current_team(user_id=user_id)
team = await memory_store.get_team_by_id(
    team_id=user_current_team.team_id if user_current_team else None
)

if not team:
    raise ValueError(f"Team configuration not found for user {user_id}")

# 現在のオーケストレーションを取得または新規作成
magentic_orchestration = await self.get_current_or_new_orchestration(
    user_id=user_id, 
    team_config=team, 
    team_switched=False  # フォローアップ質問では再作成しない
)
```

**主要ポイント:**
- **チーム構成を取得** - オーケストレーション取得前にデータベースから取得
- **チームの存在を検証** - チームが見つからない場合はエラーを発生
- **適切なファクトリメソッドを使用** - 直接アクセスではなく`get_current_or_new_orchestration()`を使用
- **チームコンテキストを渡す** - オーケストレーション作成時に渡す
- **`team_switched=False`** - フォローアップ質問でオーケストレーションを再利用することを保証
- ユーザーが実際にチームを切り替えた場合のみオーケストレーションを再作成

**これが重要な理由:**
- 各ユーザーは異なるチーム構成を持つことができる
- チームは利用可能なエージェントを決定する
- フォローアップ質問は元のタスクと同じチームを使用
- 適切なチームコンテキストにより正しいエージェントの動作を保証

**オーケストレーション再利用に関する重要な注意:**

`get_current_or_new_orchestration()` メソッド (行 94-118) に重要なロジックが含まれています：

```python
@classmethod
async def get_current_or_new_orchestration(
    cls, user_id, team_config, team_switched: bool = False
):
    """既存のオーケストレーションインスタンスを取得"""
    current_orchestration = orchestration_config.get_current_orchestration(user_id)
    
    if (
        current_orchestration is None or team_switched
    ):  # 完了時ではなく、チーム切り替え時のみ再作成
        if current_orchestration is not None and team_switched:
            # 再作成理由をログ記録
            cls.logger.info(f"Recreating orchestration for user {user_id}: team switched")
            
            # 既存のエージェントを閉じる
            for agent in current_orchestration._members:
                if agent.name != "ProxyAgent":
                    try:
                        await agent.close()
                    except Exception as e:
                        cls.logger.error("Error closing agent: %s", e)
        
        # 新しいオーケストレーションを作成
        factory = MagenticAgentFactory()
        agents = await factory.get_agents(user_id=user_id, team_config_input=team_config)
        orchestration_config.orchestrations[user_id] = await cls.init_orchestration(
            agents, user_id
        )
    
    return orchestration_config.get_current_orchestration(user_id)
```

**オーケストレーションのライフサイクル:**
1. **最初のタスク**: ユーザー用の新しいオーケストレーションを作成
2. **フォローアップ質問**: 既存のオーケストレーションを再利用 (`team_switched=False`)
3. **チーム切り替え**: 古いエージェントを閉じて新しいオーケストレーションを作成 (`team_switched=True`)
4. **タスク完了**: 再作成なし - インスタンスは次のタスクまで永続化

**再利用が機能する理由:**
- 各フォローアップ質問は**新しいプラン**と**新しいsession_id**を作成
- オーケストレーションは各新しいプランを新しいタスクとして扱う
- 各タスクが独自のplan_idを持つため状態の汚染なし
- エージェントコンテキストはユーザーセッション全体で維持
- WebSocket接続はアクティブなまま

**失敗した修正の試み:**

開発中、完了追跡と再作成を追加しようとしました：

```python
# ❌ これは機能しませんでした - 使用しないでください
if orchestration._is_completed:
    # 完了後にオーケストレーションを再作成
    orchestration = await cls.init_orchestration(agents, user_id)
    orchestration_instances[user_id] = orchestration
```

**失敗した理由:**
- オーケストレーションライフサイクルを壊すことでエージェント通信が中断
- WebSocket接続コンテキストが失われる
- エージェントが新しいリクエストに応答できない
- フレームワークがすでにタスク分離を正しく処理している

---

## フロントエンドの変更

### 2. フォローアップ質問表示コンポーネント

**ファイル:** `src/frontend/src/components/content/FollowUpQuestions.tsx`

**目的:** フォローアップ質問を解析してクリック可能なボタンとして表示

**実装:**

```typescript
export const FollowUpQuestions: React.FC<FollowUpQuestionsProps> = ({
    content,
    onQuestionClick
}) => {
    // 正規表現を使用して番号付き質問を解析
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

**主要ポイント:**
- 正規表現を使用して番号付き質問 (1., 2., 3.) を抽出
- 各質問にFluent UI Buttonを作成
- ボタンがクリックされたら`onQuestionClick`ハンドラーを呼び出す
- コンテンツに質問が見つかった場合のみレンダリング

---

### 3. フォローアップ質問クリックハンドラー

**ファイル:** `src/frontend/src/pages/PlanPage.tsx`

**行:** 625-648 `handleFollowUpQuestion()`内

**目的:** フォローアップ質問がクリックされたときに新しいプランを作成

**実装:**

```typescript
const handleFollowUpQuestion = useCallback(
    async (question: string) => {
        const id = showToast("フォローアップ質問を送信中", "progress");
        
        try {
            // session_idを自動生成するTaskServiceを使用
            const response = await TaskService.createPlan(question);
            
            dismissToast(id);
            
            if (response.plan_id) {
                // 新しいプランページに移動
                navigate(`/plan/${response.plan_id}`);
            } else {
                showToast("プランの作成に失敗しました", "error");
            }
        } catch (error: any) {
            dismissToast(id);
            showToast(
                error?.message || "プランの作成に失敗しました",
                "error"
            );
        }
    },
    [showToast, dismissToast, navigate]
);
```

**主要ポイント:**
- `TaskService.createPlan()`を使用して新しいプランを作成
- session_idを自動生成（手動ID不要）
- `/api/v3/process_request`エンドポイントを呼び出す
- 成功時に新しいプランページに移動
- 送信中にプログレストーストを表示

---

### 4. 完了したプランのチャット入力ハンドラー

**ファイル:** `src/frontend/src/pages/PlanPage.tsx`

**行:** 569-619 `handleOnchatSubmit()`内

**目的:** プランが完了したことを検出し、チャット入力を新しいプラン作成にルーティング

**実装:**

```typescript
const handleOnchatSubmit = useCallback(
    async (chatInput: string) => {
        if (!chatInput.trim()) {
            showToast("メッセージを入力してください", "error");
            return;
        }
        setInput("");

        if (!planData?.plan) return;

        // ⭐ 主要な変更: プランが完了しているかチェック
        if (planData.plan.overall_status === PlanStatus.COMPLETED) {
            const id = showToast("新しいプランを作成中", "progress");
            
            try {
                // TaskServiceを使用して新しいタスクとして送信
                const response = await TaskService.createPlan(chatInput);
                
                dismissToast(id);
                
                if (response.plan_id) {
                    // 新しいプランページに移動
                    navigate(`/plan/${response.plan_id}`);
                } else {
                    showToast("プランの作成に失敗しました", "error");
                }
            } catch (error: any) {
                dismissToast(id);
                showToast(error?.message || "プランの作成に失敗しました", "error");
            }
            return;
        }

        // それ以外の場合、進行中のプランの明確化として送信
        setSubmittingChatDisableInput(true);
        let id = showToast("明確化を送信中", "progress");

        try {
            const response = await PlanDataService.submitClarification({
                request_id: clarificationMessage?.request_id || "",
                answer: chatInput,
                plan_id: planData?.plan.id,
                m_plan_id: planApprovalRequest?.id || ""
            });
            // ... 明確化処理の残り
        }
    },
    [planData?.plan, showToast, dismissToast, loadPlanData, navigate]
);
```

**主要ポイント:**
- **プランステータスに基づく条件ロジック**:
  - `PlanStatus.COMPLETED`の場合 → 新しいプランを作成（ボタンクリックと同じ）
  - `PlanStatus.IN_PROGRESS`の場合 → 明確化を送信（既存の動作）
- チャット入力の動作をフォローアップボタンと一致させる
- ボタンハンドラーと同じ`TaskService.createPlan()`を使用
- 明確化と新しいタスクの混在を防ぐ

---

### 5. 完了時に入力を有効化して状態をクリア

**ファイル:** `src/frontend/src/pages/PlanPage.tsx`

**行:** 340-365 `FINAL_ANSWER` WebSocketハンドラー内

**目的:** プラン完了時にチャット入力を有効に保ち、保留中の明確化リクエストをクリア

**実装:**

```typescript
// FINAL_ANSWERメッセージ用のWebSocketハンドラー
useEffect(() => {
    const unsubscribe = webSocketService.on(
        WebsocketMessageType.FINAL_ANSWER, 
        (finalMessage: any) => {
            // ... メッセージ処理

            if (finalMessage?.data?.status === PlanStatus.COMPLETED) {
                setShowBufferingText(true);
                setShowProcessingPlanSpinner(false);
                setAgentMessages(prev => [...prev, agentMessageData]);
                setSelectedTeam(planData?.team || null);
                scrollToBottom();
                
                // ⭐ 主要な変更 1: フォローアップ質問用に入力を有効に保つ
                setSubmittingChatDisableInput(false);
                
                // ⭐ 主要な変更 2: 保留中の明確化状態をクリア
                setClarificationMessage(null);
                
                // プランステータスを更新
                if (planData?.plan) {
                    planData.plan.overall_status = PlanStatus.COMPLETED;
                    setPlanData({ ...planData });
                }

                processAgentMessage(agentMessageData, planData, is_final, streamingMessageBuffer);
            }
        }
    );

    return () => unsubscribe();
}, [/* 依存関係 */]);
```

**主要ポイント:**
- **入力を有効に保つ** (`setSubmittingChatDisableInput(false)`) ユーザーがフォローアップ質問を入力できるように
- **重要な変更**: これがないと、タスク完了後もチャット入力が無効のまま
- プラン完了時に`clarificationMessage`状態をクリア
- 古い明確化リクエストからの404エラーを防ぐ
- 新しいプランのためのクリーンな状態を保証
- 両方の変更が適切なフォローアップ質問処理に不可欠

---

### 6. チャットコンポーネント統合

**ファイル:** `src/frontend/src/components/content/PlanChat.tsx`

**行:** 117-126, 146

**目的:** フォローアップ質問ハンドラーをチャットコンポーネントに接続

**実装:**

```typescript
// PlanChatHeaderコンポーネント内
const handleFollowUpClick = useCallback((question: string) => {
    if (OnFollowUpQuestion) {
        // 専用のフォローアップハンドラーが利用可能な場合は使用
        OnFollowUpQuestion(question);
    } else {
        // 通常のチャット送信にフォールバック
        OnChatSubmit(question);
    }
}, [OnFollowUpQuestion, OnChatSubmit]);

// PlanChatBodyに渡す
<PlanChatBody
    planData={planData}
    input={input}
    setInput={setInput}
    submittingChatDisableInput={submittingChatDisableInput}
    OnChatSubmit={OnChatSubmit}  // 通常のチャット入力
    waitingForPlan={waitingForPlan}
    loading={false}
/>
```

**主要ポイント:**
- フォローアップ質問クリックを通常のチャット入力から分離
- 利用可能な場合は`OnFollowUpQuestion`プロップを使用
- 後方互換性のために`OnChatSubmit`にフォールバック
- クリーンなコンポーネントアーキテクチャを維持

---

## サービスレイヤーの変更

### 7. TaskService.createPlan()

**ファイル:** `src/frontend/src/services/TaskService.tsx`

**行:** 175-205

**目的:** 自動生成されたセッションIDで新しいプランを作成する一元化されたメソッド

**実装:**

```typescript
static async createPlan(
    description: string,
    teamId?: string
): Promise<InputTaskResponse> {
    // セッションIDを自動生成
    const sessionId = this.generateSessionId();
    
    // InputTaskペイロードを構築
    const inputTask: InputTask = {
        session_id: sessionId,
        description: description,
        ...(teamId && { team_id: teamId })
    };
    
    // APIエンドポイントを呼び出す
    const response = await apiService.post<InputTaskResponse>(
        apiService.ENDPOINTS.PROCESS_REQUEST,
        inputTask
    );
    
    return response;
}

// セッションID形式: "sid_" + timestamp + "_" + random
private static generateSessionId(): string {
    return `sid_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
}
```

**主要ポイント:**
- プラン作成の単一の信頼できる情報源
- 一意のセッションIDを自動生成
- 適切な`InputTask`ペイロードを構築
- `/api/v3/process_request`エンドポイントを呼び出す
- `{status, session_id, plan_id}`を返す

---

## APIエンドポイント

### 使用されるバックエンドエンドポイント:

1. **`POST /api/v3/process_request`** - 新しいプランを作成
   - **ペイロード:** `{session_id: string, description: string, team_id?: string}`
   - **使用箇所:** フォローアップ質問（ボタンとチャット入力の両方）
   - **戻り値:** `{status: string, session_id: string, plan_id: string}`

2. **`POST /api/v3/user_clarification`** - 明確化を送信
   - **ペイロード:** `{request_id: string, answer: string, plan_id: string, m_plan_id: string}`
   - **使用箇所:** プラン実行中のチャット入力（IN_PROGRESSステータス）
   - **戻り値:** 明確化レスポンス

---

## 状態管理

### 主要な状態変数:

```typescript
// プランステータス追跡
planData.plan.overall_status: PlanStatus.COMPLETED | PlanStatus.IN_PROGRESS

// 明確化追跡
clarificationMessage: ParsedUserClarification | null

// 入力制御
submittingChatDisableInput: boolean
input: string
```

### 状態フロー:

1. **プラン実行中** (`IN_PROGRESS`):
   - エージェントが入力を要求した場合、`clarificationMessage`が設定される可能性がある
   - チャット入力は明確化を送信
   - フォローアップボタンは非表示

2. **プラン完了** (`COMPLETED`):
   - `clarificationMessage`は`null`に設定
   - チャット入力は新しいプランを作成
   - フォローアップボタンが表示される
   - 入力は有効のまま

---

## バージョン追跡

### バージョン表示

**ファイル:** `src/frontend/src/version.ts`

**目的:** キャッシュ検証のためにデプロイされたバージョンを追跡

```typescript
export const APP_VERSION = '20251112-165519';
export const GIT_COMMIT = '4d2c915';
```

**表示場所:**
- `HomePage.tsx` - 右下隅
- `PlanPage.tsx` - 右下隅

**形式:** `v{APP_VERSION}` (例: "v20251112-165519")

---

## デプロイメント情報

### デプロイメント 1: 初回フォローアップ質問
- **イメージタグ:** `20251112-144059-c4fdc4a`
- **変更内容:** バックエンド生成 + フロントエンド表示コンポーネント
- **バックエンドリビジョン:** `ca-odmadevycpyl--0000010`

### デプロイメント 2: チャット入力修正
- **イメージタグ:** `20251112-152338-87812bb`
- **Gitコミット:** `87812bb`
- **変更内容:** ステータスがCOMPLETEDの場合、チャット入力が新しいプランを作成
- **バックエンドリビジョン:** `ca-odmadevycpyl--0000011`

### デプロイメント 3: 明確化状態修正
- **イメージタグ:** `20251112-165545-4d2c915`
- **Gitコミット:** `4d2c915`
- **変更内容:** 完了時に明確化状態をクリア
- **バックエンドリビジョン:** `ca-odmadevycpyl--0000012`

---

## テストシナリオ

### シナリオ 1: フォローアップボタンのクリック
1. タスクを送信（例: "売上データを分析"）
2. タスク完了を待つ
3. 3つのフォローアップ質問がボタンとして表示されることを確認
4. 任意のボタンをクリック
5. **期待される動作:** その質問で新しいプランページが開く

### シナリオ 2: カスタムフォローアップの入力
1. タスクを送信
2. タスク完了を待つ
3. チャット入力にカスタム質問を入力
4. Enterを押すか送信をクリック
5. **期待される動作:** カスタム質問で新しいプランページが開く

### シナリオ 3: 実行中の明確化
1. 明確化が必要なタスクを送信
2. エージェントが明確化を要求（プランステータス: IN_PROGRESS）
3. チャットに明確化を入力
4. Enterを押す
5. **期待される動作:** 明確化が送信され、プランが続行

### シナリオ 4: 古い明確化状態なし
1. 明確化を要求するタスクを送信
2. 明確化を提供
3. タスク完了を待つ
4. チャットにフォローアップ質問を入力
5. **期待される動作:** 新しいプランが作成される（404エラーなし）

---

### 変更の概要

### バックエンド (2ファイル変更):
1. ✅ `human_approval_manager.py` - 最終回答で3つのフォローアップ質問を生成
2. ✅ `orchestration_manager.py` - チーム構成取得と適切なオーケストレーションライフサイクル

### フロントエンド (6ファイル変更):
1. ✅ `FollowUpQuestions.tsx` - 新規: 質問をボタンとして表示
2. ✅ `PlanPage.tsx` - フォローアップクリック処理 + チャット入力ルーティング + 入力を有効に保つ
3. ✅ `PlanChat.tsx` - フォローアップハンドラーを接続
4. ✅ `TaskService.tsx` - `createPlan()`メソッドを作成
5. ✅ `HomePage.tsx` - バージョン表示を追加
6. ✅ `version.ts` - 新規: デプロイメントバージョンを追跡

### 主要なバックエンド変更:
- ✅ **チーム構成取得** - オーケストレーション作成/取得前に`run_orchestration()`内で実行
- ✅ **適切なファクトリメソッド使用** - チームコンテキスト付きで`get_current_or_new_orchestration()`
- ✅ **オーケストレーション再利用** - フォローアップ質問では`team_switched=False`
- ✅ **フォローアップ質問生成** - 最終回答に自動的に追加

### 主要なフロントエンド変更 (PlanPage.tsx):
- ✅ **入力を有効に保つ** (`setSubmittingChatDisableInput(false)`) プラン完了時
- ✅ **明確化状態をクリア** (`setClarificationMessage(null)`) プラン完了時
- ✅ **条件付きルーティング** `handleOnchatSubmit`内でプランステータスに基づく
- ✅ **新しいハンドラー** ボタンクリック用の`handleFollowUpQuestion`

### バックエンドアーキテクチャの決定:
- ✅ **オーケストレーションインスタンスの再利用** - タスク完了後に再作成しない
- ✅ **チーム対応オーケストレーション** - チーム構成を取得して検証
- ✅ **セッションベースの分離** - 各フォローアップ質問は新しいplan_idとsession_idを取得
- ✅ **状態の汚染なし** - フレームワークが分離を正しく処理

### 主要なイノベーション:
- **完了後も入力は有効のまま** - ユーザーがフォローアップ質問を入力できる
- **条件付きルーティング** - プランステータスに基づく
- **状態管理** - 古い明確化リクエストを防ぐ
- **統一された動作** - ボタンとチャット入力の両方で
- **自動生成されたセッションID** - サービスレイヤー内で
- **バージョン追跡** - デプロイメント検証用
- **オーケストレーション再利用** - フレームワークの組み込みライフサイクル管理を活用
- **チームコンテキストの保持** - フォローアップは元のタスクと同じチームを使用

---

## 結論

フォローアップ質問機能は、以下によりシームレスなユーザーエクスペリエンスを提供します：

1. ✅ 関連するフォローアップ質問を自動的に提案
2. ✅ プリセットとカスタムの両方の質問を許可
3. ✅ フォローアップを明確化として扱うのではなく、新しいプランを作成
4. ✅ プラン実行間でクリーンな状態を維持
5. ✅ 古いリクエストからの404エラーを防止

**すべての変更は後方互換性を維持** - プラン実行中の明確化は以前と同様に機能し続け、完了したプランはUIボタンと直接チャット入力の両方を通じてフォローアップ質問をサポートするようになりました。
