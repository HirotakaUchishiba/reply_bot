## 第1章: コアシステムアーキテクチャとデータフロー

  

本章では、システムの高レベルな構造と基本的なイベント処理モデルを定義します。これは、後続のすべての実装詳細の基礎となるコンテキストとして機能します。

  

### 1.1. 高レベルアーキテクチャ設計図

  

本システムは、AWS上に構築された完全サーバーレスのイベント駆動型アプリケーションです。その目的は、AIモデルを活用してEメールによる問い合わせへの返信業務を自動化し、Slackを介した人間によるレビュープロセス（Human-in-the-Loop）を組み込むことです 1。このアーキテクチャは、スケーラビリティ、コスト効率（従量課金）、および運用オーバーヘッドの削減を目的として選択されており、受信メールのような予測不能なイベントベースのトラフィックによって駆動されるワークロードに最適です。

以下に、コアコンポーネント間のデータフローを示す高レベルアーキテクチャ図を示します。

(アーキテクチャ図は、SES → Lambda → DynamoDB/OpenAI → Slack → API Gateway → Lambda → SES のフローを視覚的に表現)

  

### 1.2. コンポーネントの責務

  

アーキテクチャ内の関心事を明確に分離するため、各コンポーネントは限定的かつ明確な責務を担います。この設計は、堅牢で保守性の高いマイクロサービススタイルのアーキテクチャの基本原則に従っています 1。

- AWS Simple Email Service (SES): システムの入口（Ingress）として問い合わせメールを受信し、出口（Egress）として承認された返信メールを送信する役割を担います。
    
- AWS Lambda: すべてのコアビジネスロジックを内包する中央処理装置です。メールの解析、AIとの対話、Slackとの通信、状態管理など、アプリケーションの中核的な処理を実行します。
    
- Amazon API Gateway: Slackプラットフォームからの同期的かつインタラクティブなコールバック（ボタンクリック、モーダル送信など）を受け付けるための、セキュアなHTTPエンドポイントを提供します。
    
- Amazon DynamoDB: 複数の独立したLambda実行をまたいでEメールワークフローのコンテキストを永続化する「外部状態ストア」として機能します。
    
- Slack Platform: 運用担当者がAIによって生成された返信文案をレビュー、編集、承認するためのHuman-in-the-Loop（HITL）ユーザーインターフェースです。
    
- OpenAI API: 入力されたコンテキストに基づき、返信文案を生成する外部の大規模言語モデル（LLM）サービスです。
    

  

### 1.3. デュアルイングレス・イベントモデル

  

本アーキテクチャの核心は、「デュアルイングレス（Dual Ingress）」設計にあります。これは、単一のLambda関数が、根本的に異なる2種類のイベントソースによってトリガーされることを意味します。一つはAWS SESによる非同期的なメール受信イベント、もう一つはユーザーのSlack操作に応答するAmazon API Gateway経由の同期的なHTTPリクエストです 1。

この設計は、ビジネスロジックを単一の関数に集約することで管理を簡素化しますが、同時にその関数のエントリーポイントに極めて重要な責務を課します。Lambda関数に渡されるイベントオブジェクトは、SESからとAPI GatewayからではJSON構造が全く異なります。さらに、API Gatewayが転送するSlackのペイロードも、最初の「返信文を生成する」ボタンクリックではblock_actions、編集モーダルの送信ではview_submissionと、種類が異なります。

このため、Lambdaハンドラ関数が最初に実行すべき処理は、受信したイベントオブジェクトを検査し、そのソースとタイプを特定することです。この特定に基づき、処理を適切なビジネスロジックパス（例: handle_new_email、handle_generate_reply_click、handle_send_email_submission）に振り分けるイベントルーターの実装が必須となります。このルーターは、if/elif/else文や辞書ベースのディスパッチャを用いて実装され、システムの制御フローにおいて最も重要な部分となります。このイベントルーティングロジックの実装の不備はシステム全体の障害に直結するため、包括的なユニットテストによってその正当性を保証しなければなりません。

  

## 第2章: AIコアとデータガバナンス仕様

  

本章では、AIモデルとの連携における契約と、機密情報を含む可能性のあるEメールデータを扱う上で譲歩不可能なセキュリティ要件について詳述します。

  

### 2.1. プロンプトエンジニアリング・フレームワーク

  

本システムでは、プロンプトエンジニアリングを場当たり的な「アート」から、再現可能で保守性の高い「サイエンス」へと昇華させるための構造化されたアプローチを採用します。これにより、一貫した出力品質を確保し、プロンプトインジェクションのようなセキュリティ脆弱性のリスクを低減します 1。

- Eメールの前処理: LLMに渡すコンテキストの品質を最大化するため、署名、法的な免責事項、過去のやり取りの引用といったノイズをメール本文から除去する前処理ロジックをLambda関数内に実装します。
    
- ペルソナ定義: LLMに対し、「プロフェッショナルで、簡潔かつ丁寧なAIアシスタント」という明確な役割を与えることで、生成される文章のトーンとスタイルの一貫性を保証します。
    
- 標準化された構造: 指示、文脈、ユーザー入力を明確に分離するため、###のような区切り文字を用いた標準プロンプト構造を定義します。これは、悪意のある入力が指示として解釈されることを防ぐための重要な防御策です。
    
- テンプレート化: 様々なビジネスシナリオに対応するため、再利用可能なプロンプトテンプレートのライブラリを管理します。これにより、開発者は抽象的な概念ではなく、具体的でテスト可能なアセットを用いて開発を進めることができます。
    

|   |   |   |
|---|---|---|
|シナリオID|シナリオ概要|プロンプトテンプレート（指示部分）|
|INQUIRY_RESPONSE|顧客からの問い合わせへの一次応答|以下の顧客からの問い合わせに対し、丁寧かつ共感的に応答し、担当部署に確認の上、後ほど詳細を連絡する旨を伝えてください。|
|SCHEDULE_COORDINATION|社内での日程調整|提示された複数の候補日から、こちらの都合の良い日時を2-3個選び、相手に返信する文案を作成してください。|
|BUG_REPORT_ACK|バグ報告への感謝と対応表明|ユーザーからのバグ報告に感謝を表明し、開発チームで調査を開始したことを伝える、誠実な返信を作成してください。|
|MEETING_FOLLOWUP|会議後のフォローアップ|会議の要点を簡潔にまとめ、決定事項と次のアクションアイテムをリスト形式で記載したフォローアップメッセージを作成してください。|

  

### 2.2. OpenAI APIコントラクト

  

外部APIであるOpenAIとの連携は、コストと期待値を管理するため、厳格なJSONコントラクトとして定義します。これにより、予期せぬコスト超過を防ぎ、APIレスポンスの軽微な変更に対するアプリケーションの耐性を高めます 1。

- リクエスト仕様: OpenAI APIへのリクエストペイロードは、以下の構造に従います。max_tokensパラメータは、単一のAPIコールで発生しうるコストに明確な上限を設けるための重要なコスト管理策です。  
    JSON  
    {  
        "model": "gpt-4o",  
        "messages": [  
            {  
                "role": "user",  
                "content": "[セクション2.1で生成された完全なプロンプト文字列]"  
            }  
        ],  
        "temperature": 0.7,  
        "max_tokens": 500  
    }  
      
    
- レスポンス仕様: APIからのレスポンスは、choices.message.contentパスから生成テキストを安全に抽出することを前提とします。また、usageフィールドからトークン使用量を抽出し、コスト監視と運用のためのメトリクスとして構造化ログに出力することが義務付けられます。これは「オブザーバビリティによる運用エクセレンス」という設計原則の具体的な実践です。
    

  

### 2.3. PIIリダクション・サブシステム

  

本システムのセキュリティとデータプライバシー体制の基盤となるのが、PII（個人識別情報）リダクション・サブシステムです。Microsoftが開発したPresidioライブラリを利用し、ユーザーの生のEメールコンテンツがOpenAI APIに送信されることを構造的に防止します 1。

このサブシステムのプロセスは、単なるマスキングに留まりません。匿名化の過程で、元のPIIとプレースホルダー（例: [EMAIL_1]）の対応関係を保持するマッピング辞書、pii_mapが生成されます。AIからの応答を受信した後、このpii_mapを用いて応答文中のプレースホルダーを元のPIIに復元する「再識別化（デ・アノニマイゼーション）」が行われます。

このpii_mapの役割は、UI表示の復元だけに限定されません。本システムの非同期ワークフローにおいて、これは極めて重要な**状態（state）**となります。特に、匿名化された返信先のメールアドレスは、最終的なメール送信アクションで不可欠な情報です。このワークフローは、メール受信から返信まで複数のLambda実行にまたがり、その間には数分から数時間に及ぶ人間のレビュー時間が介在する可能性があります。したがって、pii_mapは、件名や送信者情報といった他のコンテキストと共に、DynamoDBの「外部状態ストア」に確実に永続化されなければなりません。最終的なメール送信フェーズでこのpii_mapが失われていた場合、システムは返信文案を生成できても、それを宛先に届けることができず、ビジネスプロセスは致命的な失敗に終わります。pii_mapの完全性の担保は、システムの成功に不可欠です。

  

## 第3章: Slackインターフェースとインタラクションコントラクト

  

本章では、ユーザーが直接操作するUIコンポーネントと、SlackクライアントとAWSバックエンド間の技術的なデータ交換の契約を定義します。

  

### 3.1. UIコンポーネントライブラリ (Block Kit)

  

フロントエンドとバックエンド間のすべてのインタラクションは、厳格なAPI契約として扱います。これにより、統合不全のリスクを根本的に排除し、「API・アズ・コントラクト」の設計原則を具現化します。UIコンポーネントの完全なJSON構造を以下に定義します 1。

- Eメール受信通知メッセージ: SESからイベントを受け取ったLambda関数が、指定されたSlackチャンネルに投稿する通知メッセージです。後続のアクションをトリガーするボタンのvalueフィールドには、DynamoDBに保存されたワークフロー状態への参照キーであるcontext_idが埋め込まれます。  
    JSON  
    {  
        "channel": "C12345",  
        "blocks": [  
            { "type": "header", "text": { "type": "plain_text", "text": ":email: 新規問い合わせを受信しました" } },  
            { "type": "section", "fields": [  
                { "type": "mrkdwn", "text": "*From:*\n[問い合わせユーザー名]" },  
                { "type": "mrkdwn", "text": "*Email:*\n[問い合わせユーザーのメールアドレス]" },  
                { "type": "mrkdwn", "text": "*Subject:*\n[メールの件名]" }  
            ]},  
            { "type": "section", "text": { "type": "mrkdwn", "text": "*内容:*\n>>> [メール本文の抜粋]" }},  
            { "type": "actions", "elements": [  
                {  
                    "type": "button",  
                    "text": { "type": "plain_text", "text": "返信文を生成する" },  
                    "style": "primary",  
                    "action_id": "generate_reply_action",  
                    "value": "{\"context_id\": \"uuid-goes-here\"}"  
                }  
            ]}  
        ]  
    }  
      
    
- 返信生成・編集モーダル: 「返信文を生成する」ボタンがクリックされると表示されるモーダルです。AIが生成した返信文案は、編集可能な複数行テキスト入力フィールド（plain_text_input）の初期値（initial_value）として設定されます。ユーザーはこのモーダル内で自由にテキストを編集し、Slack標準のsubmitボタンで送信します。  
    JSON  
    {  
        "type": "modal",  
        "callback_id": "ai_reply_modal_submission",  
        "private_metadata": "{\"context_id\": \"uuid-goes-here\"}",  
        "title": { "type": "plain_text", "text": "AI返信アシスタント" },  
        "submit": { "type": "plain_text", "text": "この内容でメールを送信" },  
        "close": { "type": "plain_text", "text": "閉じる" },  
        "blocks": [  
            { "type": "header", "text": { "type": "plain_text", "text": "返信文案の確認・編集" }},  
            {  
                "type": "input",  
                "block_id": "editable_reply_block",  
                "label": { "type": "plain_text", "text": "以下の返信文案を編集し、送信してください。" },  
                "element": {  
                    "type": "plain_text_input",  
                    "action_id": "editable_reply_input",  
                    "multiline": true,  
                    "initial_value": "[ここにAIが生成したテキストが入る]"  
                }  
            }  
        ]  
    }  
      
    

  

### 3.2. UIコンポーネントID命名規約

  

モーダル内の入力コンポーネントには、譲歩不可能な静的ID命名規約を導入します。これは、フロントエンド（Slack UI）とバックエンド（AWS Lambda）間のデータ交換における契約を定義するものです 1。

ユーザーがモーダルを送信すると、Slackはview_submissionペイロードをバックエンドに送信します。バックエンドのコードは、このペイロード内のview.state.valuesオブジェクトからユーザーが編集したテキストを抽出する必要があります。そのためのアクセスパスは、payload['view']['state']['values']['editable_reply_block']['editable_reply_input']['value']となります。このパスに含まれるキー（editable_reply_blockとeditable_reply_input）は、モーダルJSONで定義されたblock_idとaction_idに他なりません。

これらのIDを以下の契約で固定することにより、フロントエンドとバックエンドの開発者は互いの実装詳細を知ることなく、この契約に基づいて独立して作業を進めることが可能になります。この規約は、UIのラベルやレイアウトの変更がバックエンドのロジックを破壊することを防ぎ、並行開発を可能にする強力なエンジニアリングプラクティスです。

|   |   |   |   |
|---|---|---|---|
|コンポーネント|目的|block_id (固定値)|action_id (固定値)|
|AI返信文案入力|ユーザーによる編集内容をview_submissionペイロードから一意に特定する。|editable_reply_block|editable_reply_input|

  

### 3.3. エンドツーエンドのインタラクションシーケンス

  

Eメール受信から最終的な返信メールの送信に至るまでの、コンポーネント間のインタラクションフローを以下に示します。このシーケンスは、Lambda関数が2種類の異なるSlackイベントペイロード（block_actionsとview_submission）を処理する必要があることを明確に示しており、第1.3章で述べたイベントルーターの必要性を裏付けています 1。

  

コード スニペット

  
  

sequenceDiagram  
    participant SES  
    participant Lambda  
    participant DynamoDB  
    participant SlackClient as Slack  
    participant User  
    participant API_Gateway as API Gateway  
    participant OpenAI  
  
    SES->>Lambda: 1. メール受信イベント  
    Lambda->>DynamoDB: 2. コンテキスト(宛先, pii_map等)を保存  
    DynamoDB-->>Lambda: 3. context_idを返す  
    Lambda->>SlackClient: 4. chat.postMessage (context_idをボタンに格納)  
    User->>SlackClient: 5. 「返信文を生成する」ボタンクリック  
    SlackClient->>API_Gateway: 6. block_actionsペイロード送信  
    API_Gateway->>Lambda: 7. Lambda起動 (イベントタイプ: block_actions)  
    Lambda->>DynamoDB: 8. context_idでコンテキストを読み出し  
    Lambda->>OpenAI: 9. 匿名化済みテキストでAPIコール  
    OpenAI-->>Lambda: 10. 生成テキストを返す  
    Lambda->>Lambda: 11. テキストを再識別化  
    Lambda->>SlackClient: 12. views.open (編集可能モーダル)  
    User->>SlackClient: 13. テキストを編集し、「送信」ボタンクリック  
    SlackClient->>API_Gateway: 14. view_submissionペイロード送信  
    API_Gateway->>Lambda: 15. Lambda起動 (イベントタイプ: view_submission)  
    Lambda->>DynamoDB: 16. context_idでコンテキストを再読み出し  
    Lambda->>Lambda: 17. view.state.valuesから編集済みテキストを抽出  
    Lambda->>SES: 18. SendEmail APIコール (編集済みテキストを使用)  
    Lambda->>SlackClient: 19. 送信完了通知  
  

  

## 第4章: バックエンドインフラ設計図 (IaC with Terraform)

  

本章では、すべてのAWSバックエンドリソースの決定的な実装詳細を、Terraformを用いてコードとして定義します。これにより、再現可能でバージョン管理されたインフラストラクチャを実現します。

  

### 4.1. AWS SESおよびLambda設定

  

システムの起点となるEメール受信パイプラインと、非同期処理の回復力を保証するLambda設定を定義します 1。

- AWS SES: 送信元ドメインの認証（DKIM）を行い、特定の宛先への受信メールをLambda関数に非同期（InvocationType: "Event"）で転送するための受信ルール（Receipt Rule）を設定します。非同期呼び出しは、SESがLambdaサービスにイベントをハンドオフし、Lambda側でリトライ処理を管理できるため、回復力の観点から重要です。
    
- AWS Lambda: 非同期処理中に発生した一時的な障害やコードのバグによって顧客からの問い合わせが失われることを防ぐため、Amazon SQSキューをデッドレターキュー（DLQ）として設定することが譲歩不可能な要件です。Lambdaのデフォルトリトライがすべて失敗した場合、処理できなかったイベントはデータ損失を防ぐための最後のセーフティネットとしてDLQに送信され、手動での調査と再処理が可能になります。これは「回復力」の設計原則を直接実装するものです。
    

  

Terraform

  
  

# デッドレターキューとして使用するSQSキュー  
resource "aws_sqs_queue" "async_processing_dlq" {  
  name = "AsyncProcessingDLQ"  
}  
  
# 受信メールをLambdaに転送するルール  
resource "aws_ses_receipt_rule" "email_to_lambda_rule" {  
  name          = "EmailToLambdaRule"  
  rule_set_name = "default-rule-set"  
  recipients    = ["support@your-reply-domain.com"]  
  enabled       = true  
  lambda_action {  
    function_arn    = aws_lambda_function.main_handler.arn  
    invocation_type = "Event" # 非同期呼び出し  
  }  
}  
  
# Lambda関数の定義  
resource "aws_lambda_function" "main_handler" {  
  function_name = "MainHandler"  
  #... その他のLambda設定  
  dead_letter_config {  
    target_arn = aws_sqs_queue.async_processing_dlq.arn  
  }  
}  
  

  

### 4.2. Amazon DynamoDBデータモデル（外部状態ストア）

  

本システムは、「外部状態ストア」パターンを実装するため、DynamoDBのシングルテーブルデザインを採用します。これは、ステートレスで短命なLambda実行をまたいで、長時間にわたるワークフローの状態を管理するための解決策です 1。

メール受信時に最初のLambda関数が実行されると、Eメールのコンテキスト（返信先アドレス、件名、そして極めて重要なpii_mapなど）が一意なcontext_idをパーティションキーとしてDynamoDBの単一アイテムに保存されます。この際、TTL（Time-To-Live）属性に将来のUnixタイムスタンプが設定されます。後続のSlackインタラクションによってトリガーされるLambda関数は、ペイロードに含まれるcontext_idを使用してDynamoDBから完全なコンテキストを復元し、ワークフローを継続します。

DynamoDBのTTL機能は、単なる技術的なガベージコレクションの仕組みではありません。これは、「ユーザーはX時間以内に応答アクションを完了しなければならない」というビジネスルールの実装そのものです。TTLを超過すると、DynamoDBは自動的に状態アイテムを削除します。その後にユーザーがSlack上のボタンをクリックしても、対応する状態が存在しないためワークフローは失敗します。このTTLの値は、ユーザーの利便性と状態保存コストのバランスを考慮して慎重に決定する必要があります。

|   |   |   |   |
|---|---|---|---|
|アクセス パターンID|アクセスパターン概要|クエリ種別|キー条件式|
|AP-4|SESから受信したメールのコンテキストを一時的に保存する|書き込み|PutItem with PK=CONTEXT#{context_id}, SK=EMAIL_CONTEXT|
|AP-5|Slackからの操作時にメールのコンテキストを取得する|読み取り|GetItem with PK=CONTEXT#{context_id}, SK=EMAIL_CONTEXT|

  

### 4.3. API GatewayおよびIAM設定

  

Slackからの同期的なコールバックを受け付けるAPI Gatewayエンドポイントと、Lambda関数の実行ロールをTerraformで定義します。IAMポリシーは、最小権限の原則に厳格に従う必要があります。Lambda関数が必要とする権限は、ログの書き込み（CloudWatch Logs）、状態の読み書き（DynamoDB）、シークレットの取得（Secrets Manager）、そしてEメールの送信（SES）に限定されなければなりません 1。

  

Terraform

  
  

resource "aws_iam_role" "lambda_execution_role" {  
  name = "SlackAIBotLambdaExecutionRole"  
  #... assume_role_policy  
}  
  
resource "aws_iam_policy" "lambda_permissions" {  
  name   = "SlackAIBotLambdaPermissions"  
  policy = jsonencode({  
    Version   = "2012-10-17",  
    Statement =, Resource = aws_dynamodb_table.slack_ai_bot_table.arn },  
      { Effect = "Allow", Action = "secretsmanager:GetSecretValue", Resource = aws_secretsmanager_secret.openai_api_key.arn },  
      { Effect = "Allow", Action = "ses:SendEmail", Resource = "*" }  
    ]  
  })  
}  
  
resource "aws_iam_role_policy_attachment" "lambda_attach" {  
  role       = aws_iam_role.lambda_execution_role.name  
  policy_arn = aws_iam_policy.lambda_permissions.arn  
}  
  

  

## 第5章: 運用フレームワークとCI/CD

  

本章では、アプリケーションを迅速かつ安全に構築、デプロイし、本番環境で効果的に運用するためのプロセスとツールを定義します。

  

### 5.1. GitHub ActionsによるCI/CDパイプライン

  

すべてのインフラストラクチャはTerraformを用いてコードとして定義（Infrastructure as Code, IaC）され、アプリケーションコードと共にバージョン管理されます。CI/CDプラットフォームとしてGitHub Actionsを採用し、リポジトリへの変更をトリガーに、以下のステージで構成されるパイプラインが自動的に実行されます。これにより、手動でのデプロイエラーのリスクを劇的に削減し、すべての変更がテスト済みで再現可能であることを保証します 1。

1. Lint & Static Analysis: flake8やmypyを用いてPythonコードの品質と型安全性を静的に検証します。
    
2. Unit Tests: pytestとmotoを用いて、Lambda関数のユニットテストを実行します。
    
3. Terraform Format & Validate: IaCコードのフォーマットと構文を検証します。
    
4. Terraform Plan: 変更内容をプレビューし、ステージング環境への適用計画を作成します。
    
5. Deploy to Staging: 計画された変更をステージング環境に適用します。
    
6. Integration Tests: ステージング環境にデプロイされたコンポーネント間の連携を検証します。
    
7. Manual Approval (Optional): 本番環境へのデプロイ前に、手動での承認ステップを設けます。
    
8. Deploy to Production: 承認後、変更を本番環境にデプロイします。
    

  

### 5.2. 多層的なテスト戦略

  

アプリケーションの品質を保証するため、以下の3つの階層で構成されるテスト戦略を定義します 1。

- ユニットテスト: pytestフレームワークと、AWSサービスをローカルでシミュレートするmotoライブラリを使用します。これにより、外部依存から切り離された形で、PIIリダクションロジックなどのコアなビジネスロジックを高速に検証します。
    
- 結合テスト: ステージング環境にデプロイされた実際のAWSリソースに対し、API GatewayからLambda、DynamoDBへ至る一連のコンポーネント連携が正しく機能することを検証します。
    
- エンドツーエンド (E2E) テスト: 実際のユーザー操作を模倣し、Eメールの受信からSlackクライアント上での承認、そして最終的な返信メールの配信まで、システム全体がビジネス要件を満たしていることを確認します。
    

  

### 5.3. オブザーバビリティ・フレームワーク

  

システムの運用（Day Two）を設計の最優先事項として扱い、問題発生時に迅速に原因を特定し解決するための体系的なフレームワークを構築します 1。

1. 構造化ロギング: AWS Lambda Powertools for Pythonライブラリを採用し、すべてのログ出力を構造化されたJSON形式に標準化します。さらに、リクエストごとに一意な「相関ID（Correlation ID）」をすべてのログに自動的に含めることで、SESからLambda、OpenAIに至るまで、特定のリクエストの処理フローをサービス横断で追跡することが可能になります。
    
2. メトリクスとアラーム: システムの健全性を継続的に監視するため、以下の主要メトリクスを定義し、Amazon CloudWatchでダッシュボードとアラームを構築します。
    
3. ログ分析: 構造化ログを活用し、CloudWatch Logs Insightsを用いて高度なトラブルシューティングを行います。
    

このフレームワークにおいて、特にAWS SESの送信レピュテーションに関するメトリクス（Reputation.BounceRate、Reputation.ComplaintRate）の監視は、単なる技術的な運用ツールを超えた、戦略的なビジネスリスク管理機能となります。技術的な障害は一時的なダウンタイムを引き起こすかもしれませんが、送信ドメインのレピュテーション低下は、AWSによるSES利用停止につながる可能性があり、アプリケーションのコア機能そのものを永続的に破壊しかねません。したがって、これらのメトリクスに関するアラームは、他の技術的なアラームよりも高い優先度で扱われるべきであり、ビジネスの健全性を直接示す指標として監視されなければなりません。

|   |   |   |   |   |
|---|---|---|---|---|
|メトリクス分類|メトリクス名|AWSサービス|説明とビジネスインパクト|アラームしきい値(例)|
|技術メトリクス|Errors|Lambda|関数の実行エラー率。高い値はバグや外部サービス障害を示唆する。|5分間で1%を超える|
||Duration (p95)|Lambda|95パーセンタイルの実行時間。増加はパフォーマンス劣化を示唆する。|タイムアウト値の80%を超える|
||5XXError|API Gateway|サーバー側エラー率。高い値はバックエンド(Lambda)の問題を示唆する。|5分間で1%を超える|
|AI/コストメトリクス|ErrorRate|OpenAI (Custom)|OpenAI APIのコール失敗率。高い値はAPIキーの問題やサービス障害の可能性がある。|5分間で5%を超える|
||TotalTokens|OpenAI (Custom)|APIコールごとの合計トークン使用量。コストに直結するため、異常な増加を監視する。|1リクエストあたり1000トークンを超える|
|Eメールサービスメトリクス|Reputation.BounceRate|SES|バウンス率。高い値は送信者評価を著しく損なう。|5%を超える|
||Reputation.ComplaintRate|SES|苦情率。0.1%でも危険水域であり、アカウント停止の主因となる。|0.1%を超える|
|ビジネスメトリクス|RepliesGenerated|Custom|生成された返信の総数。ビジネス価値を測る主要な指標。|(傾向監視)|

  

## 第6章: セキュリティ実装とプレローンチ要件

  

本章では、システムが安全かつコンプライアンスに準拠した状態で本番環境にリリースされることを保証するための、具体的なチェックリストと戦略を提供します。

  

### 6.1. 環境戦略

  

安全な開発とデプロイメントを保証するため、dev（開発）、staging（検証）、prod（本番）の複数環境を分離する戦略を採用します。これらの環境は、AWSアカウントレベルで分離することを強く推奨します。この戦略を実践するための標準的なメカニズムとして、Terraform Workspacesを導入します。これにより、単一のコードベースから各環境のインフラ状態（.tfstateファイル）を個別に管理し、環境ごとの設定差分（例: Lambdaのメモリサイズ、ログレベル）は環境固有の変数ファイル（staging.tfvarsなど）で管理します 1。

  

### 6.2. プレローンチ・セキュリティチェックリスト

  

本番環境へのリリース前に、以下の項目がすべて満たされていることを確認することが必須です。このチェックリストは、第1章で定義した抽象的な設計原則（セキュリティ・バイ・デザイン、回復力など）を、具体的で検証可能なアクションに落とし込んだものです。例えば、「DLQが正しく設定されていること」は「回復力」の原則を、「SPF、DKIM、DMARCレコードが設定されていること」は「セキュリティ・バイ・デザイン」の原則を具現化し、同時にオブザーバビリティのセクションで特定されたビジネスリスクを軽減するものです 1。

- [ ] PIIリダクション: OpenAI APIに送信されるすべてのユーザー入力に対して、PIIリダクション・サブシステムが有効化され、機能していること。
    
- [ ] IAM権限: すべてのIAMロールが最小権限の原則に従って構成されていること。
    
- [ ] エラーハンドリング: 非同期処理用のLambda関数にDLQが正しく設定されていること。
    
- [ ] ドメイン認証 (必須): SESで使用する送信ドメインに、SPFおよびDKIMレコードがDNSに正しく設定・検証されていること。
    
- [ ] DMARCポリシー (必須): 送信ドメインにDMARCレコード（最低でもp=noneの監視モード）が設定されており、認証失敗を監視できること。
    
- [ ] データ暗号化: DynamoDBテーブルで保存時の暗号化（Encryption at Rest）が有効になっていること。
    
- [ ] 機密情報管理: OpenAI APIキーなどのシークレット情報が、AWS Secrets ManagerまたはParameter Storeで管理されていること。
    
- [ ] ロギング: 本番環境のLambda関数で、デバッグレベルの詳細なイベントログが無効化されていること。
    
- [ ] 依存関係: 使用しているすべてのサードパーティライブラリについて、既知の脆弱性がないかスキャンされていること。
    

#### 引用文献

1. 設計仕様書
    

**