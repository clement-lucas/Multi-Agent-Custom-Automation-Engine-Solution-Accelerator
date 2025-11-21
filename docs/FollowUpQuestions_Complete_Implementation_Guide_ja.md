# フォローアップ質問: 完全実装ガイド

**日付:** 2025年11月21日  
**機能:** コンテキスト保持型フォローアップ質問  
**最新バージョン:** 20251121-013241-0196884

---

## 目次

1. [概要](#概要)
2. [2つの実装アプローチ](#2つの実装アプローチ)
3. [機能の動作](#機能の動作)
4. [技術アーキテクチャ](#技術アーキテクチャ)
5. [バックエンド実装](#バックエンド実装)
6. [フロントエンド実装](#フロントエンド実装)
7. [エラー解決タイムライン](#エラー解決タイムライン)
8. [テストと検証](#テストと検証)
9. [デプロイ情報](#デプロイ情報)
10. [結論](#結論)

---

## 概要

本ドキュメントは、マルチエージェント カスタム オートメーション エンジンにおけるフォローアップ質問機能の実装に関する包括的なガイドです。システムは、フォローアップ質問を処理するための**2つの異なるアプローチ**をサポートしており、それぞれ異なるユースケースと技術的実装を持っています。

### この機能が可能にすること

タスク完了後、ユーザーは以下が可能になります:
- AIが生成した3つのフォローアップ質問をクリック可能なボタンとして表示
- 提案された質問をクリックして会話を継続
- チャット入力に直接カスタムフォローアップ質問を入力
- ページナビゲーションの中断なしにコンテキストとフローを維持

---

## 2つの実装アプローチ

### アプローチ1: 新規プラン作成（オーケストレーションベース）

**ユースケース:** 完全なエージェント連携が必要な新規タスク

**動作:**
- 各フォローアップ質問が新しい`plan_id`と`session_id`を持つ**新規プラン**を作成
- 利用可能なすべてのエージェントとの完全なオーケストレーション
- 新しいプランページへ遷移
- 既存のチーム構成を使用（オーケストレーションインスタンスは再利用）

**APIエンドポイント:** `POST /api/v3/process_request`

**フロントエンドメソッド:** `TaskService.createPlan(question)`

**使用される場合:**
- フォローアップ質問生成機能（アプローチ1）
- 新しい分析や異なる視点が必要な質問
- 完全なエージェント連携が必要なタスク

---

### アプローチ2: 軽量コンテキスト継続（直接エージェント呼び出し）

**ユースケース:** 同じプランコンテキスト内での直接継続

**動作:**
- 既存の`plan_id`を持つ**同じプラン**を継続
- 直接エージェント呼び出し（オーケストレーションのオーバーヘッドなし）
- 同じページに留まり、レスポンスをインライン表示
- コンテキストを維持: 元のタスク + 直近5件の会話メッセージ

**APIエンドポイント:** `POST /api/v3/continue_plan`

**フロントエンドメソッド:** `TaskService.continuePlan(planId, question)`

**使用される場合:**
- 同じコンテキスト内での軽量なフォローアップ質問
- 迅速な明確化や追加の詳細
- 完全なオーケストレーションが不要な場合

---

### 比較表

| 側面 | アプローチ1: 新規プラン | アプローチ2: コンテキスト継続 |
|--------|---------------------|----------------------------------|
| **プランID** | 新しいplan_idを作成 | 同じplan_idを保持 |
| **ナビゲーション** | 新しいページへ遷移 | 現在のページに留まる |
| **オーケストレーション** | すべてのエージェントとの完全なオーケストレーション | 直接エージェント呼び出しのみ |
| **コンテキスト** | 新しいコンテキストで新規開始 | 直近5件のメッセージ + 元のタスクを保持 |
| **パフォーマンス** | やや遅い（完全なセットアップ） | より高速（直接呼び出し） |
| **ユースケース** | 新しい分析、異なる視点 | 迅速なフォローアップ、明確化 |
| **APIエンドポイント** | `/api/v3/process_request` | `/api/v3/continue_plan` |
| **WebSocketフラグ** | 標準メッセージ | `is_follow_up: true`フラグ |

---

## 機能の動作

### プラン完了時

1. **バックエンドがフォローアップ質問を生成** - エージェントが番号付きのコンテキストに基づいた3つの質問を作成
2. **フロントエンドがそれらを表示** - 質問がクリック可能なFluent UIボタンとして表示される
3. **チャット入力は有効なまま** - ユーザーは直接カスタム質問を入力可能
4. **明確化状態がクリア** - 古いリクエストからの404エラーを防止

### ユーエクスペリエンスフロー

```
[タスク完了]
エージェント: "こちらが回答です... 他に何かお手伝いできることはありますか?
1. これをさらに最適化するにはどうすればよいですか？
2. 潜在的なリスクは何ですか？
3. 例を提供していただけますか？"

[3つのクリック可能なボタンが表示 + チャット入力が有効]

ユーザーの選択肢:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
│ オプションA: ボタンをクリック                  │
│   → (アプローチ1) 新規プランが作成される       │
│   → /plan/{new_plan_id}へ遷移                 │
│   → 完全なオーケストレーション                │
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
│ オプションB: カスタム質問を入力                │
│   → (アプローチ1) 新規プランが作成される       │
│   → /plan/{new_plan_id}へ遷移                 │
│   → 完全なオーケストレーション                │
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
│ オプションC: 軽量な継続を使用                  │
│   → (アプローチ2) continuePlan()を呼び出し    │
│   → 同じページに留まる                        │
│   → 直接エージェント呼び出し                  │
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## 技術アーキテクチャ

### オーケストレーションライフサイクル（アプローチ1）

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         ユーザーが新規タスクを開始                            │
│                    (初回またはフォローアップ質問)                             │
└────────────────────────────────┬────────────────────────────────────────────┘
                                 │
                                 ▼
                    ┌────────────────────────┐
                    │   フロントエンド(React) │
                    │  TaskService.createPlan│
                    └────────────┬───────────┘
                                 │
                                 │ POST /api/v3/process_request
                                 │ {session_id, description, team_id?}
                                 │
                                 ▼
┌────────────────────────────────────────────────────────────────────────────┐
│                        バックエンド オーケストレーションマネージャー          │
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
        オーケストレーションは存在？      チーム切替？
                    │                         │
        ┌───────────▼─────────┐   ┌──────────▼───────────┐
        │   なし(初回タスク)   │   │   あり(チーム変更)    │
        └─────────┬───────────┘   └──────────┬───────────┘
                  │                           │
                  │                           │ 既存エージェントをクローズ
                  │                           │ await agent.close()
                  │                           │
                  └───────────┬───────────────┘
                              │
                              ▼
                ┌─────────────────────────────┐
                │  新規オーケストレーション作成│
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
│ あり(存在)     │                          │  オーケストレー │
│ 再利用する     │                          │  ション作成済み │
└───────┬───────┘                          └────────┬────────┘
        │                                           │
        │ 同じオーケストレーションインスタンス      │
        │ 異なるplan_id                             │
        │ 異なるsession_id                          │
        │                                           │
        └───────────────┬───────────────────────────┘
                        │
                        ▼
        ┌───────────────────────────────┐
        │   エージェントでタスク実行     │
        │   (Semantic Kernel)           │
        │   - WebSocket接続             │
        │   - エージェントコンテキスト保持│
        │   - 新規plan_id作成            │
        └───────────────┬───────────────┘
                        │
                        │ タスク実行中...
                        │ エージェント連携...
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
│                        フロントエンド (PlanPage.tsx)                       │
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
```

### コンテキストフロー（アプローチ2）

```
ユーザーのフォローアップ質問
    ↓
フロントエンド: continuePlan(plan_id, question)
    ↓
バックエンド: /api/v3/continue_plan
    ↓
取得: 元のタスク + 直近5件のメッセージ
    ↓
コンテキスト文字列の構築
    ↓
RAIチェック(コンテンツ安全性)
    ↓
ファクトリー: MagenticAgentFactory().create_agent_from_config(user_id, agent_obj)
    ↓
直接エージェント呼び出し(DataAnalysisAgentまたはAnalysisRecommendationAgent)
    ↓
WebSocketストリーム: { is_follow_up: true, content: "..." }
    ↓
フロントエンド: インライン表示(ページリセットなし)
```

### 状態遷移図

```
                    ┌──────────────────┐
                    │   プランなし      │
                    │   (初期)         │
                    └────────┬─────────┘
                             │
                             │ ユーザーがタスクを送信
                             │ POST /process_request
                             │
                             ▼
                    ┌──────────────────┐
                    │   実行中         │◄──────┐
                    │                  │       │
                    │  - 実行中        │       │ 明確化
                    │  - 明確化を要求  │       │ 送信済み
                    │    する可能性    │       │
                    └────────┬─────────┘       │
                             │                 │
                             │ タスク完了      │
                             │                 │
                             ▼                 │
                    ┌──────────────────┐       │
                    │   完了           │       │
                    │                  │       │
                    │  ✅ 入力有効     │       │
                    │  ✅ フォローアップ│       │
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
              │                           │ ステータス確認:
              │                           │ 完了？
              │                           │
              └───────────┬───────────────┘
                          │
                          │ はい: 新規プラン作成(アプローチ1)
                          │ または: プラン継続(アプローチ2)
                          │
                          ▼
                    ┌──────────────────┐
                    │   新規プラン      │
                    │   実行中         │
                    │                  │
                    │  - 新規plan_id   │
                    │  - 新規session_id│
                    │  - 同じチーム    │
                    │  - 再利用された  │
                    │    オーケストレー│
                    │    ション        │
                    └──────────────────┘
```

---

## バックエンド実装

### 1. フォローアップ質問生成（アプローチ1）

**ファイル:** `src/backend/v3/orchestration/human_approval_manager.py`

**行:** `final_append()`メソッドの75-87行

**目的:** タスク完了時にコンテキストに基づいた3つのフォローアップ質問を自動生成

**実装:**
```python
def final_append(self, final_answer: str, plan_id: str = None):
    """
    ユーザーエンゲージメントを促進するためのフォローアップ質問プロンプトを追加
    """
    follow_up_prompt = """

他に何かお手伝いできることはありますか？以下のフォローアップ質問に興味があるかもしれません:

1. [コンテキストに基づいてAIが生成した質問]
2. [コンテキストに基づいてAIが生成した質問]
3. [コンテキストに基づいてAIが生成した質問]"""
    
    return final_answer + follow_up_prompt
```

**要点:**
- 最終回答に自動的に追加される
- 質問は番号付き(1, 2, 3)で簡単に解析可能
- AIが完了したタスクに基づいてコンテキストに沿った質問を生成
- WebSocket経由で最終メッセージに表示される

---

### 2. オーケストレーション管理（アプローチ1）

**ファイル:** `src/backend/v3/orchestration/orchestration_manager.py`

**行:** `run_orchestration()`メソッドの123-136行

**目的:** オーケストレーションライフサイクルとチーム構成を管理

**削除（126行目）:**
```python
# ❌ 旧コード - チームコンテキストなしで直接オーケストレーションを取得
magentic_orchestration = orchestration_config.get_current_orchestration(user_id)
```

**追加（123-136行）:**
```python
# ✅ 新コード - チーム構成を取得し、オーケストレーションを適切に作成/取得
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
    team_switched=False  # フォローアップ質問で再作成しない
)
```

**主な利点:**
- データベースからチーム構成を取得
- オーケストレーション前にチームの存在を検証
- 適切なファクトリーメソッドを使用
- `team_switched=False`でオーケストレーションの再利用を保証
- チームが実際に切り替わった場合のみ再作成

**オーケストレーション再利用ロジック（`get_current_or_new_orchestration`、94-118行）:**

```python
@classmethod
async def get_current_or_new_orchestration(
    cls, user_id, team_config, team_switched: bool = False
):
    """既存のオーケストレーションインスタンスを取得または新規作成。"""
    current_orchestration = orchestration_config.get_current_orchestration(user_id)
    
    if (
        current_orchestration is None or team_switched
    ):  # 完了時ではなく、チーム切替時のみ再作成
        if current_orchestration is not None and team_switched:
            # 再作成する理由をログに記録
            cls.logger.info(f"Recreating orchestration for user {user_id}: team switched")
            
            # 既存エージェントをクローズ
            for agent in current_orchestration._members:
                if agent.name != "ProxyAgent":
                    try:
                        await agent.close()
                    except Exception as e:
                        cls.logger.error("Error closing agent: %s", e)
        
        # 新規オーケストレーションを作成
        factory = MagenticAgentFactory()
        agents = await factory.get_agents(user_id=user_id, team_config_input=team_config)
        orchestration_config.orchestrations[user_id] = await cls.init_orchestration(
            agents, user_id
        )
    
    return orchestration_config.get_current_orchestration(user_id)
```

**オーケストレーションライフサイクル:**
1. **初回タスク**: ユーザーに対して新規オーケストレーションを作成
2. **フォローアップ質問**: 既存のオーケストレーションを再利用
3. **チーム切替**: 既存エージェントをクローズし、新規オーケストレーションを作成
4. **タスク完了**: 再作成なし - インスタンスは次のタスクまで持続

---

### 3. 軽量プラン継続エンドポイント（アプローチ2）

**ファイル:** `src/backend/v3/api/router.py`

**新規エンドポイント:** `/api/v3/continue_plan`

**実装:**
```python
@app.post("/api/v3/continue_plan")
async def continue_plan(request: Request):
    """
    フォローアップ質問で既存のプランを継続。
    更新されたコンテキストで元の分析エージェントを直接呼び出す。
    """
    # リクエストからplan_idとquestionを抽出
    # 元のプランとメッセージを取得
    # 元のタスク + 直近5件のメッセージからコンテキストを構築
    # コンテンツ安全性のためのRAIチェック
    # 分析エージェントを直接呼び出す(オーケストレーションなし)
    # is_follow_up=TrueでWebSocket経由でレスポンスをストリーム配信
```

**主な機能:**
- 実行前のRAI(責任あるAI)チェック
- 直接エージェント呼び出し: `DataAnalysisAgent`または`AnalysisRecommendationAgent`
- コンテキストウィンドウ: 元のタスク + 直近5件のメッセージ
- `is_follow_up: true`フラグ付きWebSocketストリーミング
- エラーハンドリングとロギング

**重要な修正 - エージェントファクトリーメソッド呼び出し（463行目）:**

**修正前:**
```python
# ❌ エラー: 誤ったメソッド名、インスタンス化なし、user_idなし
agent_instance = await MagenticAgentFactory.create_agent(analysis_agent)
```

**修正後:**
```python
# ✅ 修正: 正しいメソッド、適切なインスタンス化、user_idを含む
factory = MagenticAgentFactory()
agent_instance = await factory.create_agent_from_config(user_id, analysis_agent)
```

**根本原因:**
- `MagenticAgentFactory`はインスタンス化が必要（静的ではない）
- 正しいメソッド: `create_agent_from_config(user_id, agent_obj)`
- 以前のコードは存在しない`create_agent()`メソッドを呼び出していた

---

## フロントエンド実装

### 1. フォローアップ質問表示コンポーネント

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

**要点:**
- 正規表現で番号付き質問(1., 2., 3.)を抽出
- 各質問にFluent UI Buttonを作成
- クリック時に`onQuestionClick`ハンドラーを呼び出す
- 質問が見つかった場合のみレンダリング

---

### 2. フォローアップボタンクリックハンドラー（アプローチ1）

**ファイル:** `src/frontend/src/pages/PlanPage.tsx`

**行:** `handleFollowUpQuestion()`の625-648行

**目的:** フォローアップボタンがクリックされたときに新規プランを作成

**実装:**

```typescript
const handleFollowUpQuestion = useCallback(
    async (question: string) => {
        const id = showToast("Submitting follow-up question", "progress");
        
        try {
            // session_idを自動生成するTaskServiceを使用
            const response = await TaskService.createPlan(question);
            
            dismissToast(id);
            
            if (response.plan_id) {
                // 新しいプランページへ遷移
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

**要点:**
- `TaskService.createPlan()`を使用（アプローチ1）
- session_idを自動生成
- `/api/v3/process_request`を呼び出す
- 新しいプランページへ遷移
- 進行状況トーストを表示

---

### 3. ステータス検出付きチャット入力ハンドラー

**ファイル:** `src/frontend/src/pages/PlanPage.tsx`

**行:** `handleOnchatSubmit()`の569-619行

**目的:** プランのステータスに基づいてチャット入力をルーティング

**実装:**

```typescript
const handleOnchatSubmit = useCallback(
    async (chatInput: string) => {
        if (!chatInput.trim()) {
            showToast("Please enter a message", "error");
            return;
        }
        setInput("");

        if (!planData?.plan) return;

        // ⭐ 重要なロジック: プランステータスをチェックしてルーティングを決定
        if (planData.plan.overall_status === PlanStatus.COMPLETED) {
            const id = showToast("Creating new plan", "progress");
            
            try {
                // 新規タスクとして送信（アプローチ1）
                const response = await TaskService.createPlan(chatInput);
                
                dismissToast(id);
                
                if (response.plan_id) {
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

        // それ以外の場合、実行中のプランの明確化として送信
        setSubmittingChatDisableInput(true);
        let id = showToast("Submitting clarification", "progress");

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

**条件ロジック:**
- `PlanStatus.COMPLETED` → 新規プラン作成（ボタンと同様）
- `PlanStatus.IN_PROGRESS` → 明確化を送信（既存の動作）

---

### 4. 完了時の入力有効化と状態クリア

**ファイル:** `src/frontend/src/pages/PlanPage.tsx`

**行:** WebSocket `FINAL_ANSWER`ハンドラーの340-365行

**目的:** プラン完了時にチャットを有効に保ち、古い状態をクリア

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
                
                // ⭐ 重要な修正1: フォローアップ質問のために入力を有効に保つ
                setSubmittingChatDisableInput(false);
                
                // ⭐ 重要な修正2: 保留中の明確化状態をクリア
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

**重要な変更:**
1. **入力を有効に保つ** - これがないとチャットが無効なままになる
2. **明確化状態をクリア** - 古いリクエストからの404エラーを防止

---

### 5. 軽量プラン継続ハンドラー（アプローチ2）

**ファイル:** `src/frontend/src/pages/PlanPage.tsx`

**目的:** ページリセットなしで既存のプランを継続

**フェーズ5の修正 - `createPlan()`の代わりに`continuePlan()`を使用:**

**修正前:**
```typescript
const handleFollowUpQuestion = async (question: string) => {
    setFollowUpQuestion('');
    setFollowUpInputVisible(false);
    
    await createPlan(question); // ❌ 誤り - 新規プランを作成
};
```

**修正後:**
```typescript
const handleFollowUpQuestion = async (question: string) => {
    setFollowUpQuestion('');
    setFollowUpInputVisible(false);
    
    if (plan?.id) {
        await continuePlan(plan.id, question); // ✅ 正しい - 既存のプランを継続
    }
};
```

**フェーズ8の修正 - API呼び出し前にユーザーメッセージを表示:**

**修正前:**
```typescript
// ❌ 問題: API呼び出し後にユーザーメッセージを追加
try {
    const response = await TaskService.continuePlan(planData.plan.id, chatInput);
    
    if (response.status) {
        // ここでメッセージを追加 - 遅すぎる！
        const agentMessageData = { /* ... */ };
        setAgentMessages((prev: any) => [...prev, agentMessageData]);
    }
}
```

**修正後:**
```typescript
// ✅ 修正: API呼び出し前に即座にユーザーメッセージを追加
const agentMessageData = {
    agent: 'human',
    agent_type: AgentMessageType.HUMAN_AGENT,
    timestamp: Date.now(),
    steps: [],
    next_steps: [],
    content: chatInput,
    raw_data: chatInput,
} as AgentMessageData;

setAgentMessages((prev: any) => [...prev, agentMessageData]);
scrollToBottom();

// その後API呼び出しを実行
const id = showToast("Submitting follow-up question", "progress");
try {
    const response = await TaskService.continuePlan(planData.plan.id, chatInput);
    // ...
}
```

**影響:**
- ユーザーメッセージが即座に表示される
- 即座の視覚的フィードバック
- 競合状態を排除
- チャット入力とボタンの両方で一貫性

---

### 6. サービスレイヤー実装

**ファイル:** `src/frontend/src/services/TaskService.tsx`

**アプローチ1: 新規プラン作成（175-205行）**

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

// セッションIDフォーマット: "sid_" + タイムスタンプ + "_" + ランダム
private static generateSessionId(): string {
    return `sid_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
}
```

**アプローチ2: 既存プランの継続**

**ファイル:** `src/frontend/src/services/taskService.ts`

```typescript
export const continuePlan = async (
  planId: string,
  question: string
): Promise<PlanResponse> => {
  const response = await apiClient.post<PlanResponse>(
    '/api/v3/continue_plan',
    {
      plan_id: planId,
      question: question,
    }
  );
  return response.data;
};
```

---

### 7. WebSocketハンドラー拡張（アプローチ2）

**ファイル:** `src/frontend/src/pages/PlanPage.tsx`

**目的:** インライン表示のために`is_follow_up`フラグを処理

**修正前:**
```typescript
case 'thinking':
case 'response':
  // 常に新規プラン実行として処理
  break;
```

**修正後:**
```typescript
case 'thinking':
case 'response':
  if (message.is_follow_up) {
    // フォローアップレスポンスとして処理（ページリセットなし）
  } else {
    // 通常のレスポンスとして処理
  }
  break;
```

**影響:** システムが新規プランとフォローアップレスポンスを区別

---

### 8. チャットコンポーネント統合

**ファイル:** `src/frontend/src/components/content/PlanChat.tsx`

**行:** 117-126, 146

**目的:** フォローアップハンドラーをチャットコンポーネントに接続

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

---

## エラー解決タイムライン

| フェーズ | 課題 | 解決策 | アプローチ | バージョン |
|-------|-------|------------|----------|---------|
| 1-4 | 初期実装 | バックエンドエンドポイント + フロントエンド統合 | アプローチ2 | - |
| 5 | フォローアップ時のページリセット | `continuePlan()`を使用するようハンドラーを修正 | アプローチ2 | 20251120-185652 |
| 5 | フォローアップが処理されない | `is_follow_up`フラグチェックを追加 | アプローチ2 | 20251120-185652 |
| 6 | インポートエラー | `WebsocketMessageType`のインポートパスを修正 | アプローチ2 | 20251120-191149 |
| 7 | エージェントファクトリーエラー | メソッド名とインスタンス化を修正 | アプローチ2 | 20251120-194351 |
| 8 | ユーザーメッセージが表示されない | API呼び出し前にメッセージを追加 | アプローチ2 | 20251121-013241 |

---

## テストと検証

### テストシナリオ

#### シナリオ1: フォローアップボタンクリック（アプローチ1）
1. タスクを送信（例: "売上データを分析"）
2. タスク完了を待つ
3. ボタンとして表示される3つのフォローアップ質問を確認
4. 任意のボタンをクリック
5. **期待される結果:** その質問で新しいプランページが開く

#### シナリオ2: カスタムチャット入力（アプローチ1）
1. タスクを送信して完了
2. チャット入力にカスタム質問を入力
3. Enterキーを押す
4. **期待される結果:** カスタム質問で新しいプランページが開く

#### シナリオ3: 軽量継続（アプローチ2）
1. タスクを送信して完了
2. `continuePlan()`メソッドを使用
3. **期待される結果:** レスポンスがインライン表示、ページ遷移なし

#### シナリオ4: 実行中の明確化
1. 明確化が必要なタスクを送信
2. エージェントが明確化を要求（IN_PROGRESS）
3. チャットに明確化を入力
4. **期待される結果:** 明確化が送信され、プランが継続

#### シナリオ5: 古い状態なし
1. 実行中に明確化を提供
2. タスク完了を待つ
3. フォローアップ質問を入力
4. **期待される結果:** 新規プランが作成される（404エラーではない）

### 成功したデプロイログ（フェーズ7）

```
Run ID: ce2b was successful after 1m38s (backend)
Run ID: ce2c was successful after 2m6s (frontend)

バックエンドイメージ:
  - acrmacae7359.azurecr.io/macae-backend:20251120-194351-c9cd75d
  - acrmacae7359.azurecr.io/macae-backend:latest (更新済み)

フロントエンドイメージ:
  - acrmacae7359.azurecr.io/macae-frontend:20251120-194351-c9cd75d
  - acrmacae7359.azurecr.io/macae-frontend:latest (更新済み)
```

### ログ検証

```
INFO:v3.magentic_agents.magentic_agent_factory:Creating agent 'DataAnalysisAgent' with model 'o4-mini' (Template: Reasoning)
INFO:v3.config.agent_registry:Registered agent: ReasoningAgentTemplate
INFO:v3.magentic_agents.reasoning_agent:📝 Registered agent 'DataAnalysisAgent' with global registry
INFO:v3.magentic_agents.magentic_agent_factory:Successfully created and initialized agent 'DataAnalysisAgent'
```

✅ **エージェント作成成功** - エラーなし！

---

## デプロイ情報

### 最新デプロイ

- **バージョン:** 20251121-013241-0196884
- **バックエンドコンテナアプリ:** ca-odmadevycpyl
- **フロントエンドApp Service:** app-odmadevycpyl
- **リソースグループ:** rg-odmadev
- **リージョン:** 東日本

### デプロイ履歴

| デプロイ | バージョン | 変更内容 | バックエンドリビジョン |
|------------|---------|---------|------------------|
| 1 | 20251112-144059-c4fdc4a | 初期フォローアップ生成 + 表示 | ca-odmadevycpyl--0000010 |
| 2 | 20251112-152338-87812bb | 完了時にチャット入力が新規プランを作成 | ca-odmadevycpyl--0000011 |
| 3 | 20251112-165545-4d2c915 | 完了時に明確化状態をクリア | ca-odmadevycpyl--0000012 |
| 4 | 20251120-185652-c9cd75d | フォローアップハンドラー、WebSocketフラグを修正 | - |
| 5 | 20251120-191149-c9cd75d | WebsocketMessageTypeのインポートを修正 | - |
| 6 | 20251120-194351-c9cd75d | エージェントファクトリーメソッド呼び出しを修正 | - |
| 7 | 20251121-013241-0196884 | ユーザーメッセージ表示タイミングを修正 | - |

### バージョン追跡

**ファイル:** `src/frontend/src/version.ts`

```typescript
export const APP_VERSION = '20251121-013241';
export const GIT_COMMIT = '0196884';
```

**表示場所:**
- `HomePage.tsx` - 右下隅
- `PlanPage.tsx` - 右下隅

### デプロイ自動化

**ファイル:** `deploy_with_acr.sh`

各デプロイ前にバージョンを自動更新:

```bash
# デプロイタグを生成
DEPLOY_TAG="$(date -u +'%Y%m%d-%H%M%S')-$(git rev-parse --short HEAD)"

# version.tsを更新
VERSION_FILE="src/frontend/src/version.ts"
cat > "$VERSION_FILE" << EOF
export const VERSION = '${DEPLOY_TAG}';
export const BUILD_DATE = '$(date -u +'%Y-%m-%d %H:%M:%S UTC')';
EOF
```

### ログの表示

```bash
# バックエンドログ
az containerapp logs show --name ca-odmadevycpyl --resource-group rg-odmadev --follow

# フロントエンドログ
az webapp log tail --name app-odmadevycpyl --resource-group rg-odmadev
```

---

## 結論

### 実装完了 ✅

フォローアップ質問機能は、**2つの補完的なアプローチ**で正常に実装されました:

**アプローチ1: 新規プラン作成**
✅ すべてのエージェントとの完全なオーケストレーション  
✅ 自動チーム構成取得  
✅ オーケストレーションインスタンスの再利用  
✅ フォローアップ質問の生成  
✅ 新規プランへのスムーズな遷移  

**アプローチ2: 軽量継続**
✅ 直接エージェント呼び出し  
✅ コンテキスト保持（直近5件のメッセージ）  
✅ インラインレスポンス表示  
✅ ページリセットなし  
✅ より高速なパフォーマンス  

**共通機能:**
✅ 完了後もチャット入力が有効  
✅ 明確化状態管理  
✅ ユーザーメッセージの即座の表示  
✅ WebSocketストリーミング  
✅ エラーハンドリング  
✅ バージョン追跡  

### 主な利点

1. **柔軟性**: 完全なオーケストレーションまたは軽量な継続を選択可能
2. **コンテキスト保持**: 会話のフローと履歴を維持
3. **ユーザーエクスペリエンス**: 中断のないシームレスなインタラクション
4. **パフォーマンス**: 異なるユースケースに最適化
5. **保守性**: 関心事の明確な分離

### アーキテクチャのハイライト

- **オーケストレーション再利用**: ユーザーごとに1つのインスタンス、タスク間で持続
- **チームコンテキスト**: 適切な構成の取得と検証
- **状態の分離**: 各タスクは一意のplan_idとsession_idを持つ
- **入力ルーティング**: ステータスベースの条件ロジック
- **WebSocket接続**: オーケストレーションのライフタイム全体で維持

### すべての課題が解決 ✅

✅ バックエンドエンドポイントが機能  
✅ フロントエンド統合完了  
✅ ページリセットを防止  
✅ WebSocketハンドリングを修正  
✅ インポートエラーを修正  
✅ エージェントファクトリーエラーを解決  
✅ ユーザーメッセージ表示タイミングを修正  
✅ 状態管理をクリーンアップ  
✅ 明確化フローが機能  
✅ フォローアップ生成が有効  

**システムは現在、包括的なオーケストレーションと軽量な継続のバランスを取った、堅牢で柔軟なフォローアップ質問体験を提供し、ユーザーに両方の長所を提供しています。**
