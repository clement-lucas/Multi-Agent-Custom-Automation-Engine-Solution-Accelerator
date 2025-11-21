# フォローアップ質問実装サマリー

**日付:** 2025年11月20日  
**機能:** コンテキスト保持型フォローアップ質問  
**デプロイバージョン:** 20251120-194351-c9cd75d

## 概要

本ドキュメントは、ユーザーがページをリセットしたりコンテキストを失ったりすることなく、同じプラン実行内でフォローアップ質問を行えるようにする軽量なフォローアップ質問機能の実装についてまとめたものです。本実装は、オーケストレーションのオーバーヘッドなしに直接エージェントを呼び出すことに重点を置いています。

---

## 問題の定義

**元の課題:**
- ユーザーが同じプランのコンテキスト内でフォローアップ質問をしたい
- 以前の実装では、フォローアップ質問を受け取った後にページがリセットされていた
- フォローアップ質問が正しく処理されていなかった
- システムエラーによりフォローアップの実行が妨げられていた

---

## 実装アプローチ

### 設計思想
- **軽量実装:** オーケストレーションなしの直接エージェント呼び出し
- **コンテキスト保持:** 元のタスク + 直近5件の会話メッセージを維持
- **ページリセットなし:** フォローアップレスポンスをナビゲーションなしでインライン表示
- **最小限の変更:** 可能な限り既存インフラを活用

---

## 実施した変更

### フェーズ1-4: 初期実装(以前のセッション)

#### 1. バックエンドAPIエンドポイント
**ファイル:** `src/backend/v3/api/router.py`

**新規エンドポイント:** `/api/v3/continue_plan`

```python
@app.post("/api/v3/continue_plan")
async def continue_plan(request: Request):
    """
    フォローアップ質問で既存のプランを継続する。
    更新されたコンテキストで元の分析エージェントを直接呼び出す。
    """
    # リクエストからplan_idとquestionを抽出
    # 元のプランとメッセージを取得
    # 元のタスク + 直近5件のメッセージからコンテキストを構築
    # 分析エージェントを直接呼び出す(オーケストレーションなし)
    # WebSocket経由でis_follow_up=Trueでレスポンスをストリーム配信
```

**主要機能:**
- 実行前のRAI(責任あるAI)チェック
- 直接エージェント呼び出し(DataAnalysisAgentまたはAnalysisRecommendationAgent)
- コンテキストウィンドウ: 元のタスク説明 + 直近5件のメッセージ
- `is_follow_up: true`フラグ付きWebSocketストリーミング
- エラーハンドリングとロギング

#### 2. フロントエンドAPI統合
**ファイル:** `src/frontend/src/services/taskService.ts`

**新規メソッド:**
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

#### 3. デプロイ自動化
**ファイル:** `deploy_with_acr.sh`

**機能強化:** 各デプロイ前にversion.tsを自動更新

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

---

### フェーズ5: フロントエンド修正(以前のセッション)

**課題:** フォローアップ質問を受け取った後、アプリケーションがメインページをリセットし、フォローアップ質問が処理されていなかった。

#### 1. フォローアップボタンハンドラー修正
**ファイル:** `src/frontend/src/pages/PlanPage.tsx`

**変更:** `handleFollowUpQuestion`が`createPlan()`の代わりに`continuePlan()`を呼び出すように修正

**修正前:**
```typescript
const handleFollowUpQuestion = async (question: string) => {
  setFollowUpQuestion('');
  setFollowUpInputVisible(false);
  
  await createPlan(question); // ❌ 誤り - 新しいプランを作成
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

**影響:** フォローアップボタンが新しいプランを作成する代わりに、既存のプランを正しく継続するようになりました。

#### 2. WebSocketハンドラー修正
**ファイル:** `src/frontend/src/pages/PlanPage.tsx`

**変更:** `is_follow_up`フラグをチェックするようにWebSocketメッセージハンドラーを更新

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
    // フォローアップレスポンスとして処理(ページリセットなし)
  } else {
    // 通常のレスポンスとして処理
  }
  break;
```

**影響:** システムが新規プランレスポンスとフォローアップレスポンスを区別し、ページリセットを防止するようになりました。

**デプロイ:** バージョン 20251120-185652-c9cd75d

---

### フェーズ6: インポートエラー修正(以前のセッション)

**課題:** `ImportError: cannot import name 'WebsocketMessageType'`でデプロイが失敗

#### インポートパス修正
**ファイル:** `src/backend/v3/api/router.py`

**修正前:**
```python
from common.models.messages_kernel import WebsocketMessageType
```

**修正後:**
```python
from v3.models.messages import WebsocketMessageType
```

**根本原因:** モジュールが移動/リファクタリングされたが、インポート文が更新されていなかった。

**デプロイ:** バージョン 20251120-191149-c9cd75d

---

### フェーズ7: エージェントファクトリーエラー修正(現在のセッション)

**課題:** フォローアップ質問を送信後、`continue_plan`エンドポイントがエラーをスロー:
```
ERROR:v3.api.router:Error continuing plan: type object 'MagenticAgentFactory' has no attribute 'create_agent'
```

#### エージェントファクトリーメソッド呼び出し修正
**ファイル:** `src/backend/v3/api/router.py` (463行目)

**修正前:**
```python
from v3.magentic_agents.magentic_agent_factory import MagenticAgentFactory

# 分析エージェントを直接呼び出す
agent_instance = await MagenticAgentFactory.create_agent(analysis_agent)
# ❌ エラー: create_agent()メソッドが存在しない
# ❌ エラー: ファクトリーのインスタンス化が欠落
# ❌ エラー: user_idパラメータが欠落
```

**修正後:**
```python
from v3.magentic_agents.magentic_agent_factory import MagenticAgentFactory

# 分析エージェントを直接呼び出す
factory = MagenticAgentFactory()
agent_instance = await factory.create_agent_from_config(user_id, analysis_agent)
# ✅ 修正: 正しいメソッド名
# ✅ 修正: ファクトリーのインスタンス化を追加
# ✅ 修正: user_idパラメータを含む
```

**根本原因分析:**
1. `MagenticAgentFactory`はインスタンス化が必要なクラス
2. 正しいメソッドは`create_agent_from_config(user_id: str, agent_obj: SimpleNamespace)`
3. 以前のコードは存在しない静的メソッド`create_agent()`を呼び出そうとしていた

**ログからのエラーパターン:**
- 19:22:09、19:22:31、19:23:13、19:24:03、19:30:18に複数発生
- パターン: RAIチェック成功 → エージェント作成失敗 → HTTP 500エラー
- すべてのフォローアップ試行が同じエラーで失敗

**ソースからの検証:**
```python
# src/backend/v3/magentic_agents/magentic_agent_factory.py
class MagenticAgentFactory:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self._agent_list: List = []
    
    async def create_agent_from_config(
        self, 
        user_id: str, 
        agent_obj: SimpleNamespace
    ) -> Union[FoundryAgentTemplate, ReasoningAgentTemplate, ProxyAgent]:
        # 設定からエージェントを作成
```

**デプロイ:** バージョン 20251120-194351-c9cd75d

---

### フェーズ8: ユーザーメッセージ表示修正(2025年11月21日)

**課題:** チャット入力またはフォローアップボタンから送信されたフォローアップ質問が、チャットUI上のユーザーメッセージとして表示されていなかった。

**根本原因:** ユーザーメッセージがAPI呼び出し完了後にチャットに追加されていたため、以下のタイミング問題が発生:
- 遅延やエラーがあった場合、メッセージが表示されない可能性
- WebSocketレスポンスがユーザーメッセージ表示前に到着する可能性
- AIレスポンスが表示される前にユーザーが自分の質問を見ることができない

#### 即時メッセージ表示修正
**ファイル:** `src/frontend/src/pages/PlanPage.tsx`

**変更1: チャット入力ハンドラー(`handleOnchatSubmit`)**

**修正前:**
```typescript
// プランが完了している場合、コンテキスト付きで同じプランを継続
if (planData.plan.overall_status === PlanStatus.COMPLETED) {
    const id = showToast("Submitting follow-up question", "progress");
    
    try {
        const response = await TaskService.continuePlan(
            planData.plan.id,
            chatInput
        );
        
        dismissToast(id);
        
        if (response.status) {
            showToast("Follow-up question submitted successfully", "success");
            
            // 処理中であることを示すようにUI状態を更新
            setSubmittingChatDisableInput(true);
            setShowProcessingPlanSpinner(true);
            
            // ❌ 問題: API呼び出し後にユーザーメッセージを追加
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
```

**修正後:**
```typescript
// プランが完了している場合、コンテキスト付きで同じプランを継続
if (planData.plan.overall_status === PlanStatus.COMPLETED) {
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
    
    const id = showToast("Submitting follow-up question", "progress");
    
    // 処理中であることを示すようにUI状態を更新
    setSubmittingChatDisableInput(true);
    setShowProcessingPlanSpinner(true);
    
    try {
        const response = await TaskService.continuePlan(
            planData.plan.id,
            chatInput
        );
        
        dismissToast(id);
        
        if (response.status) {
            showToast("Follow-up question submitted successfully", "success");
```

**変更2: フォローアップボタンハンドラー(`handleFollowUpQuestion`)**

**修正前:**
```typescript
const handleFollowUpQuestion = useCallback(
    async (question: string) => {
        if (!question.trim()) {
            return;
        }

        if (!planData?.plan) return;

        const id = showToast("Submitting follow-up question", "progress");

        try {
            const response = await TaskService.continuePlan(
                planData.plan.id,
                question
            );
            
            dismissToast(id);
            
            if (response.status) {
                showToast("Follow-up question submitted successfully", "success");
                
                // 処理中であることを示すようにUI状態を更新
                setSubmittingChatDisableInput(true);
                setShowProcessingPlanSpinner(true);
                
                // ❌ 問題: API呼び出し後にユーザーメッセージを追加
                const agentMessageData = {
                    agent: 'human',
                    agent_type: AgentMessageType.HUMAN_AGENT,
                    timestamp: Date.now(),
                    steps: [],
                    next_steps: [],
                    content: question,
                    raw_data: question,
                } as AgentMessageData;
                
                setAgentMessages((prev: any) => [...prev, agentMessageData]);
                scrollToBottom();
```

**修正後:**
```typescript
const handleFollowUpQuestion = useCallback(
    async (question: string) => {
        if (!question.trim()) {
            return;
        }

        if (!planData?.plan) return;

        // ✅ 修正: API呼び出し前に即座にユーザーメッセージを追加
        const agentMessageData = {
            agent: 'human',
            agent_type: AgentMessageType.HUMAN_AGENT,
            timestamp: Date.now(),
            steps: [],
            next_steps: [],
            content: question,
            raw_data: question,
        } as AgentMessageData;
        
        setAgentMessages((prev: any) => [...prev, agentMessageData]);
        scrollToBottom();

        const id = showToast("Submitting follow-up question", "progress");

        // 処理中であることを示すようにUI状態を更新
        setSubmittingChatDisableInput(true);
        setShowProcessingPlanSpinner(true);

        try {
            const response = await TaskService.continuePlan(
                planData.plan.id,
                question
            );
            
            dismissToast(id);
            
            if (response.status) {
                showToast("Follow-up question submitted successfully", "success");
```

**影響:**
- ユーザーメッセージがチャットUIに即座に表示される
- API呼び出し前にメッセージが表示され、即座の視覚的フィードバックを保証
- チャットでの入力かフォローアップボタンのクリックかにかかわらず一貫した動作
- ユーザーの質問の前にAIレスポンスが表示される可能性のある競合状態を排除

**デプロイ:** バージョン 20251121-013241-0196884

---

## 技術アーキテクチャ

### コンテキストフロー
```
ユーザーの質問
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

### メッセージフォーマット
```typescript
interface WebSocketMessage {
  type: 'thinking' | 'response' | 'error' | 'complete';
  content: string;
  is_follow_up?: boolean;  // フォローアップレスポンス用の新しいフラグ
  plan_id?: string;
}
```

---

## テストと検証

### 成功したデプロイログ(フェーズ7)
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

### ログからの検証
```
INFO:v3.magentic_agents.magentic_agent_factory:Creating agent 'DataAnalysisAgent' with model 'o4-mini' (Template: Reasoning)
INFO:v3.config.agent_registry:Registered agent: ReasoningAgentTemplate
INFO:v3.magentic_agents.reasoning_agent:📝 Registered agent 'DataAnalysisAgent' with global registry
INFO:v3.magentic_agents.magentic_agent_factory:Successfully created and initialized agent 'DataAnalysisAgent'
```

✅ **エージェント作成成功** - `'MagenticAgentFactory' has no attribute 'create_agent'`エラーは発生していません!

---

## 主要なメリット

1. **コンテキスト保持:** ユーザーが会話のコンテキストを失うことなくフォローアップ質問が可能
2. **ページリセットなし:** レスポンスがインラインで表示され、ユーザーフローを維持
3. **軽量:** オーケストレーションのオーバーヘッドなし、直接エージェント呼び出し
4. **高速レスポンス:** 直接エージェント実行による最小限のレイテンシ
5. **保守性:** 既存のエージェントインフラを活用

---

## エラー解決タイムライン

| フェーズ | 課題 | 解決策 | バージョン |
|-------|-------|------------|---------|
| 1-4 | 初期実装 | バックエンドエンドポイント + フロントエンド統合 | - |
| 5 | フォローアップ時のページリセット | `continuePlan()`を使用するようハンドラーを修正 | 20251120-185652 |
| 5 | フォローアップが処理されない | `is_follow_up`フラグチェックを追加 | 20251120-185652 |
| 6 | インポートエラー | WebsocketMessageTypeのインポートパスを修正 | 20251120-191149 |
| 7 | エージェントファクトリーエラー | メソッド名とインスタンス化を修正 | 20251120-194351 |
| 8 | ユーザーメッセージが表示されない | API呼び出し後ではなく前にメッセージを追加 | 20251121-013241 |

---

## 変更されたファイル

### バックエンド
- `src/backend/v3/api/router.py` - `/api/v3/continue_plan`エンドポイントを追加、インポートを修正、エージェントファクトリー呼び出しを修正

### フロントエンド
- `src/frontend/src/services/taskService.ts` - `continuePlan()`メソッドを追加
- `src/frontend/src/pages/PlanPage.tsx` - フォローアップハンドラーとWebSocket処理を修正

### インフラストラクチャ
- `deploy_with_acr.sh` - 自動バージョン更新を追加
- `src/frontend/src/version.ts` - 各デプロイ時に自動生成

---

## 使用方法

### ユーザー向け
1. タスク/プラン実行を完了
2. 「フォローアップ質問をする」ボタンをクリックするか、チャット入力を使用
3. フォローアップ質問を入力
4. ページリセットなしでレスポンスがインラインで表示される
5. 元のタスクからのコンテキストが保持される

### 開発者向け
```python
# バックエンド: プラン継続エンドポイント
POST /api/v3/continue_plan
{
  "plan_id": "uuid-of-plan",
  "question": "What about trends?"
}

# レスポンス: is_follow_up=trueのWebSocketストリーム
```

```typescript
// フロントエンド: プラン継続メソッド
await continuePlan(planId, question);
```

---

## 今後の機能強化

1. **会話履歴UI:** 完全な会話スレッドを表示
2. **コンテキストウィンドウ設定:** ユーザーがコンテキストサイズを調整可能に
3. **マルチターン最適化:** より高速な後続呼び出しのためのエージェント状態のキャッシュ
4. **分析:** フォローアップ使用パターンの追跡

---

## デプロイ情報

- **現在のバージョン:** 20251121-013241-0196884
- **バックエンドコンテナアプリ:** ca-odmadevycpyl
- **フロントエンドApp Service:** app-odmadevycpyl
- **リソースグループ:** rg-odmadev
- **リージョン:** 東日本

### ログの表示
```bash
# バックエンドログ
az containerapp logs show --name ca-odmadevycpyl --resource-group rg-odmadev --follow

# フロントエンドログ
az webapp log tail --name app-odmadevycpyl --resource-group rg-odmadev
```

---

## 結論

フォローアップ質問機能は、軽量でコンテキスト保持型のアプローチで正常に実装されました。すべての技術的課題が解決されました:

✅ バックエンドエンドポイントが機能  
✅ フロントエンド統合完了  
✅ ページリセット問題を修正  
✅ WebSocketハンドリングを修正  
✅ インポートエラーを解決  
✅ エージェントファクトリーエラーを修正  
✅ ユーザーメッセージ表示タイミングを修正  

システムは、完全なオーケストレーションの複雑さなしに、同じプランコンテキスト内でシームレスなフォローアップ質問をサポートするようになり、より良いユーザー体験を提供します。ユーザーは、チャット入力またはフォローアップ提案ボタンをクリックすることでフォローアップ質問ができ、AIレスポンスが到着する前にメッセージがチャットUIに即座に表示されます。
