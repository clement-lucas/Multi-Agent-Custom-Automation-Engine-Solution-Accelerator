# プランステップにおけるエージェント名の表示

## 概要

本ドキュメントは、フロントエンドアプリケーションでプランナーがプランを作成する際に、各タスクの前にエージェント名を表示するために行われた変更をまとめたものです。

## 課題

以前は、マルチエージェントプランナーがプランを作成した際、プランステップにはタスクの説明のみが表示され、どのエージェントが各タスクを実行するかが示されていませんでした。これにより、ユーザーは各ステップのエージェント割り当てを理解することが困難でした。

**変更前:**
```
1. 業界データを収集する
2. 競合他社の価格を分析する
3. 推奨事項を生成する
```

**変更後:**
```
1. [EnhancedResearchAgent] 業界データを収集する
2. [DataAnalysisAgent] 競合他社の価格を分析する
3. [RecommendationAgent] 推奨事項を生成する
```

## バックエンドアーキテクチャ

### プラン解析 (`plan_to_mplan_converter.py`)

バックエンドパーサーは、プランテキストからエージェント名を抽出し、別々に保存します：

- **エージェント抽出メソッド:**
  - `_try_bold_agent()`: `**AgentName**` パターンからエージェントを抽出
  - `_try_window_agent()`: 最初の25文字内でのフォールバック検出
  - `_extract_agent_and_action()`: (エージェント名, クリーニングされたアクションテキスト) のタプルを返す

- **データ構造:**
  ```python
  MStep(
      agent="EnhancedResearchAgent",  # エージェント名は別に保存
      action="業界データを収集する"      # エージェント名を含まないクリーンなアクションテキスト
  )
  ```

パーサーは抽出後にアクションテキストからエージェント名を削除し、別の `agent` フィールドに保存します。

## フロントエンドの変更

### 変更されたファイル

1. **`src/frontend/src/components/content/streaming/StreamingPlanResponse.tsx`**
2. **`src/frontend/src/components/content/PlanPanelRight.tsx`**

### 実装の詳細

#### StreamingPlanResponse.tsx

**場所:** 216-228行目（ステップ抽出ロジック）

**変更内容:**
```typescript
// ステップデータからエージェント名を抽出
const agent = step.agent || 'System';
const action = step.action || step.cleanAction || '';

// フォーマット: [AgentName] action
const displayText = `[${agent}] ${action.trim()}`;

// フォーマットされたテキストを保存
planSteps.push({ 
    type: action.trim().endsWith(':') ? 'heading' : 'substep', 
    text: displayText 
});
```

#### PlanPanelRight.tsx

**場所:** 38-51行目（ステップ抽出ロジック）

**変更内容:**
```typescript
return planApprovalRequest.steps.map((step, index) => {
    const action = step.action || step.cleanAction || '';
    const agent = step.agent || 'System';
    const isHeading = action.trim().endsWith(':');
    
    // フォーマット: [AgentName] action
    const displayText = `[${agent}] ${action.trim()}`;

    return {
        text: displayText,
        isHeading,
        key: `${index}-${action.substring(0, 20)}`
    };
}).filter(step => step.text.length > 0);
```

## 表示形式

### 選択された形式: `[AgentName]`

エージェント名はアクションテキストの前に角括弧で囲まれて表示されます：
- **形式:** `[AgentName] アクションの説明`
- **例:** `[EnhancedResearchAgent] 複数のソースから業界データを収集する`

### 検討された代替形式

1. **太字マークダウン:** `**AgentName** action` - プレーンテキスト表示では太字にレンダリングされない
2. **HTML Strongタグ:** `<strong>AgentName</strong> action` - スタイル付きではなくリテラルテキストとしてレンダリングされる
3. **インラインスタイル:** `fontWeight: 700` を持つ別々のReact要素 - より複雑な実装
4. **括弧（選択）:** `[AgentName] action` - クリーンでシンプル、普遍的に視認可能

## メリット

1. **明確なエージェント割り当て:** ユーザーは各タスクを担当するエージェントを即座に確認できる
2. **理解の向上:** マルチエージェントワークフローの理解が向上する
3. **透明性の強化:** プラン実行戦略がより明確になる
4. **一貫した表示:** すべてのプラン表示コンポーネントで機能する

## テスト

変更を確認するには：

1. 更新されたフロントエンドコードでアプリケーションをデプロイ
2. 新しいマルチエージェントプランリクエストを作成
3. プランステップがエージェント名を括弧付きで表示することを確認
4. ストリーミングプランレスポンスとプランパネル右側の両方の表示を確認

## 今後の機能強化

検討すべき潜在的な改善点：

1. **色分け:** 異なるエージェントタイプに対する異なる色
2. **エージェントアイコン:** エージェント名の横に視覚的なアイコン
3. **ツールチップ:** 各エージェントの役割を説明するホバー説明
4. **フィルタリング:** エージェント別にプランステップをフィルタリングする機能
5. **太字スタイリング:** エージェント名に対する適切なReactベースの太字スタイリングを実装

## 関連ファイル

- **バックエンドパーサー:** `src/backend/v3/orchestration/helper/plan_to_mplan_converter.py`
- **プランプロンプト:** `src/backend/v3/orchestration/human_approval_manager.py`
- **フロントエンド表示:** `src/frontend/src/components/content/streaming/StreamingPlanResponse.tsx`
- **プランパネル:** `src/frontend/src/components/content/PlanPanelRight.tsx`
- **データモデル:** `src/frontend/src/models/` (MPlanData, MStepインターフェース)

## デプロイメント

これらの変更を行った後、アプリを再デプロイしてください。デプロイメントが完了すると、変更がフロントエンドアプリケーションに反映されます。
