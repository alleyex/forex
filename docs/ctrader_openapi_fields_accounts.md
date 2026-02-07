# cTrader Open API（帳戶主題）欄位清單

本檔案依官方 Open API 文件整理（描述為中文意譯，來源為官方描述）。

## Messages（帳戶/認證/Token）

### ProtoOAApplicationAuthReq

用途：應用程式向 cTrader Proxy 進行授權。  

| Field | Type | Label | 官方描述（意譯） |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | Optional | Payload 類型。 |
| clientId | string | Required | 註冊時取得的 Client ID。 |
| clientSecret | string | Required | 註冊時取得的 Client Secret。 |

### ProtoOAApplicationAuthRes

用途：對 `ProtoOAApplicationAuthReq` 的回應。  

| Field | Type | Label | 官方描述（意譯） |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | Optional | Payload 類型。 |

### ProtoOAAccountAuthReq

用途：授權交易帳戶會話（需先完成 Application 授權）。  

| Field | Type | Label | 官方描述（意譯） |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | Optional | Payload 類型。 |
| ctidTraderAccountId | int64 | Required | cTrader 平台交易帳戶唯一 ID。 |
| accessToken | string | Required | 提供帳戶存取的 Access Token。 |

### ProtoOAAccountAuthRes

用途：對 `ProtoOAAccountAuthReq` 的回應。  

| Field | Type | Label | 官方描述（意譯） |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | Optional | Payload 類型。 |
| ctidTraderAccountId | int64 | Required | cTrader 平台交易帳戶唯一 ID。 |

### ProtoOAAccountDisconnectEvent

用途：帳戶會話在伺服器端被中斷時的事件（需重新授權）。  

| Field | Type | Label | 官方描述（意譯） |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | Optional | Payload 類型。 |
| ctidTraderAccountId | int64 | Required | cTrader 平台交易帳戶唯一 ID。 |

### ProtoOAAccountLogoutReq

用途：請求登出交易帳戶會話。  

| Field | Type | Label | 官方描述（意譯） |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | Optional | Payload 類型。 |
| ctidTraderAccountId | int64 | Required | cTrader 平台交易帳戶唯一 ID。 |

### ProtoOAAccountLogoutRes

用途：對 `ProtoOAAccountLogoutReq` 的回應（實際登出會由 `ProtoOAAccountDisconnectEvent` 完成）。  

| Field | Type | Label | 官方描述（意譯） |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | Optional | Payload 類型。 |
| ctidTraderAccountId | int64 | Required | cTrader 平台交易帳戶唯一 ID。 |

### ProtoOAAccountsTokenInvalidatedEvent

用途：特定帳戶的 session 被終止、但其他帳戶連線仍維持時的事件。  

| Field | Type | Label | 官方描述（意譯） |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | Optional | Payload 類型。 |
| ctidTraderAccountIds | RepeatedField<int64> | Repeated | 受影響的帳戶 ID 清單。 |
| reason | string | Optional | 斷線原因（例如 Token 過期或撤銷）。 |

### ProtoOAGetAccountListByAccessTokenReq

用途：用 Access Token 取得已授權的帳戶列表。  

| Field | Type | Label | 官方描述（意譯） |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | Optional | Payload 類型。 |
| accessToken | string | Required | 帳戶存取用的 Access Token。 |

### ProtoOAGetAccountListByAccessTokenRes

用途：對 `ProtoOAGetAccountListByAccessTokenReq` 的回應。  

| Field | Type | Label | 官方描述（意譯） |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | Optional | Payload 類型。 |
| accessToken | string | Required | 帳戶存取用的 Access Token。 |
| permissionScope | ProtoOAClientPermissionScope | Optional | Token 的權限範圍（SCOPE_VIEW / SCOPE_TRADE）。 |
| ctidTraderAccount | RepeatedField<ProtoOACtidTraderAccount> | Repeated | 帳戶列表。 |

### ProtoOAGetCtidProfileByTokenReq

用途：用 Access Token 取得 Trader 的 Profile（受 GDPR 限制）。  

| Field | Type | Label | 官方描述（意譯） |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | Optional | Payload 類型。 |
| accessToken | string | Required | 帳戶存取用的 Access Token。 |

### ProtoOAGetCtidProfileByTokenRes

用途：對 `ProtoOAGetCtidProfileByTokenReq` 的回應。  

| Field | Type | Label | 官方描述（意譯） |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | Optional | Payload 類型。 |
| profile | ProtoOACtidProfile | Required | Trader Profile。 |

### ProtoOARefreshTokenReq

用途：用 Refresh Token 取得新的 Access Token。  

| Field | Type | Label | 官方描述（意譯） |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | Optional | Payload 類型。 |
| refreshToken | string | Required | 用於更新 Access Token 的 Refresh Token。 |

### ProtoOARefreshTokenRes

用途：對 `ProtoOARefreshTokenReq` 的回應（包含新的 Token 組）。  

| Field | Type | Label | 官方描述（意譯） |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | Optional | Payload 類型。 |
| accessToken | string | Required | 新的 Access Token。 |
| tokenType | string | Required | Token 類型（bearer）。 |
| expiresIn | int64 | Required | Access Token 有效秒數。 |
| refreshToken | string | Required | 新的 Refresh Token。 |

### ProtoOATraderReq

用途：取得 Trader 帳戶資料。  

| Field | Type | Label | 官方描述（意譯） |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | Optional | Payload 類型。 |
| ctidTraderAccountId | int64 | Required | 交易帳戶 ID。 |

### ProtoOATraderRes

用途：對 `ProtoOATraderReq` 的回應。  

| Field | Type | Label | 官方描述（意譯） |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | Optional | Payload 類型。 |
| ctidTraderAccountId | int64 | Required | 交易帳戶 ID。 |
| trader | ProtoOATrader | Required | Trader 帳戶資訊。 |

### ProtoOATraderUpdatedEvent

用途：Trader 帳戶在伺服器端更新時的事件。  

| Field | Type | Label | 官方描述（意譯） |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | Optional | Payload 類型。 |
| ctidTraderAccountId | int64 | Required | 交易帳戶 ID。 |
| trader | ProtoOATrader | Required | Trader 帳戶資訊。 |

## Model Messages（帳戶相關）

### ProtoOAClientPermissionScope (ENUM)

| Name | Value | 官方描述（意譯） |
|---|---|---|
| SCOPE_VIEW | 0 | 僅可查詢（不可交易）。 |
| SCOPE_TRADE | 1 | 可交易（允許所有指令）。 |

### ProtoOAAccessRights (ENUM)

| Name | Value | 官方描述（意譯） |
|---|---|---|
| FULL_ACCESS | 0 | 允許所有交易。 |
| CLOSE_ONLY | 1 | 只允許平倉。 |
| NO_TRADING | 2 | 僅檢視。 |
| NO_LOGIN | 3 | 無存取權。 |

### ProtoOAAccountType (ENUM)

| Name | Value | 官方描述（意譯） |
|---|---|---|
| HEDGED | 0 | 同一商品允許多筆持倉。 |
| NETTED | 1 | 同一商品只允許一筆持倉。 |
| SPREAD_BETTING | 2 | Spread Betting 帳戶類型。 |

### ProtoOACtidProfile

| Field | Type | Label | 官方描述（意譯） |
|---|---|---|---|
| userId | int64 | Required | Trader 使用者 ID（GDPR 限制，僅提供此欄位）。 |

### ProtoOACtidTraderAccount

| Field | Type | Label | 官方描述（意譯） |
|---|---|---|---|
| ctidTraderAccountId | uint64 | Required | 交易帳戶唯一 ID。 |
| isLive | bool | Optional | 是否為真實帳戶；若是需使用 live host。 |
| traderLogin | int64 | Optional | 交易登入 ID（顯示於 UI）。 |
| lastClosingDealTimestamp | int64 | Optional | 最後一次平倉成交時間（毫秒）。 |
| lastBalanceUpdateTimestamp | int64 | Optional | 最後一次餘額更新時間（毫秒）。 |
| brokerTitleShort | string | Optional | Broker 簡稱（UI 顯示）。 |

### ProtoOALimitedRiskMarginCalculationStrategy (ENUM)

| Name | Value | 官方描述（意譯） |
|---|---|---|
| ACCORDING_TO_LEVERAGE | 0 | 依槓桿計算。 |
| ACCORDING_TO_GSL | 1 | 依保證止損計算。 |
| ACCORDING_TO_GSL_AND_LEVERAGE | 2 | 依保證止損與槓桿計算。 |

### ProtoOAStopOutStrategy (ENUM)

| Name | Value | 官方描述（意譯） |
|---|---|---|
| MOST_MARGIN_USED_FIRST | 0 | 先平掉使用保證金最多的持倉。 |
| MOST_LOSING_FIRST | 1 | 先平掉虧損最嚴重的持倉。 |

### ProtoOATotalMarginCalculationType (ENUM)

| Name | Value | 官方描述（意譯） |
|---|---|---|
| MAX | 0 | MAX。 |
| SUM | 1 | SUM。 |
| NET | 2 | NET。 |

### ProtoOATrader

| Field | Type | Label | 官方描述（意譯） |
|---|---|---|---|
| ctidTraderAccountId | int64 | Required | 交易帳戶 ID（回應配對用）。 |
| balance | int64 | Required | 目前帳戶餘額。 |
| balanceVersion | int64 | Optional | 餘額版本號（餘額變更時遞增）。 |
| managerBonus | int64 | Optional | Broker 提供的獎金金額。 |
| ibBonus | int64 | Optional | IB 獎金金額。 |
| nonWithdrawableBonus | int64 | Optional | 不可提領的獎金。 |
| accessRights | ProtoOAAccessRights | Optional | 帳戶存取權限。 |
| depositAssetId | int64 | Required | 帳戶入金幣別。 |
| swapFree | bool | Optional | 是否為伊斯蘭（免隔夜利息）帳戶。 |
| leverageInCents | uint32 | Optional | 槓桿（1:50 以 5000 表示）。 |
| totalMarginCalculationType | ProtoOATotalMarginCalculationType | Optional | 帳戶保證金計算方式。 |
| maxLeverage | uint32 | Optional | 允許的最大槓桿。 |
| frenchRisk | bool | Optional | 是否為 AMF 合規帳戶。 |
| traderLogin | int64 | Optional | 交易登入 ID（伺服器內唯一）。 |
| accountType | ProtoOAAccountType | Optional | 帳戶類型（HEDGED/NETTED/…）。 |
| brokerName | string | Optional | Broker 指派的白牌名稱。 |
| registrationTimestamp | int64 | Optional | 帳戶註冊時間（毫秒）。 |
| isLimitedRisk | bool | Optional | 是否為有限風險帳戶（需保證止損）。 |
| limitedRiskMarginCalculationStrategy | ProtoOALimitedRiskMarginCalculationStrategy | Optional | 有限風險帳戶的保證金策略。 |
| moneyDigits | uint32 | Optional | 金額倍率指數（影響餘額/獎金等顯示）。 |
| fairStopOut | bool | Optional | 是否為完整平倉或部分平倉的 Stop Out。 |
| stopOutStrategy | ProtoOAStopOutStrategy | Optional | Stop Out 持倉選擇策略。 |

## Common Messages（通用）

### ProtoErrorRes

| Field | Type | Label | 官方描述（意譯） |
|---|---|---|---|
| payloadType | ProtoPayloadType | Optional | Payload 類型。 |
| errorCode | string | Required | ProtoErrorCode 或自訂錯誤碼名稱。 |
| description | string | Optional | 錯誤說明。 |
| maintenanceEndTimestamp | uint64 | Optional | 維護結束的 Unix 毫秒時間。 |

### ProtoHeartbeatEvent

| Field | Type | Label | 官方描述（意譯） |
|---|---|---|---|
| payloadType | ProtoPayloadType | Optional | Payload 類型。 |

### ProtoMessage

| Field | Type | Label | 官方描述（意譯） |
|---|---|---|---|
| payloadType | uint32 | Required | PayloadType 或自訂 PayloadType 的 ID。 |
| payload | bytes | Optional | 對應 payloadType 的序列化訊息。 |
| clientMsgId | string | Optional | 客戶端自訂的 request id，回應會帶回。 |

## Common Model Messages（通用）

### ProtoErrorCode (ENUM)

> 此 ENUM 的完整條目很多，請參見官方 Common Model Messages 表。

### ProtoPayloadType (ENUM)

> 此 ENUM 的完整條目很多，請參見官方 Common Model Messages 表。
