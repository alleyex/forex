# cTrader Open API Account Topics Field List

This file is compiled from the official Open API documentation. Descriptions are English paraphrases derived from the official text.

## Messages (Accounts, Authentication, and Tokens)

### ProtoOAApplicationAuthReq

Purpose: Application authorizes with the cTrader Proxy.  

| Field | Type | Label | Official description (paraphrased) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | Optional | Payload type. |
| clientId | string | Required | Client ID obtained during registration. |
| clientSecret | string | Required | Client Secret obtained during registration. |

### ProtoOAApplicationAuthRes

Purpose: Response to `ProtoOAApplicationAuthReq`.  

| Field | Type | Label | Official description (paraphrased) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | Optional | Payload type. |

### ProtoOAAccountAuthReq

Purpose: Authorize a trading account session (requires prior application authorization).  

| Field | Type | Label | Official description (paraphrased) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | Optional | Payload type. |
| ctidTraderAccountId | int64 | Required | Unique trading account ID on the cTrader platform. |
| accessToken | string | Required | Access token that grants account access. |

### ProtoOAAccountAuthRes

Purpose: Response to `ProtoOAAccountAuthReq`.  

| Field | Type | Label | Official description (paraphrased) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | Optional | Payload type. |
| ctidTraderAccountId | int64 | Required | Unique trading account ID on the cTrader platform. |

### ProtoOAAccountDisconnectEvent

Purpose: Event emitted when the account session is interrupted on the server side and must be re-authorized.  

| Field | Type | Label | Official description (paraphrased) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | Optional | Payload type. |
| ctidTraderAccountId | int64 | Required | Unique trading account ID on the cTrader platform. |

### ProtoOAAccountLogoutReq

Purpose: Request logout of a trading account session.  

| Field | Type | Label | Official description (paraphrased) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | Optional | Payload type. |
| ctidTraderAccountId | int64 | Required | Unique trading account ID on the cTrader platform. |

### ProtoOAAccountLogoutRes

Purpose: Response to `ProtoOAAccountLogoutReq` (the actual logout completes via `ProtoOAAccountDisconnectEvent`).  

| Field | Type | Label | Official description (paraphrased) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | Optional | Payload type. |
| ctidTraderAccountId | int64 | Required | Unique trading account ID on the cTrader platform. |

### ProtoOAAccountsTokenInvalidatedEvent

Purpose: Event emitted when one specific account session is terminated while other account connections remain active.  

| Field | Type | Label | Official description (paraphrased) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | Optional | Payload type. |
| ctidTraderAccountIds | RepeatedField<int64> | Repeated | List of affected account IDs. |
| reason | string | Optional | Disconnect reason, for example token expiration or revocation. |

### ProtoOAGetAccountListByAccessTokenReq

Purpose: Get the list of authorized accounts using an access token.  

| Field | Type | Label | Official description (paraphrased) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | Optional | Payload type. |
| accessToken | string | Required | Access token used for account access. |

### ProtoOAGetAccountListByAccessTokenRes

Purpose: Response to `ProtoOAGetAccountListByAccessTokenReq`.  

| Field | Type | Label | Official description (paraphrased) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | Optional | Payload type. |
| accessToken | string | Required | Access token used for account access. |
| permissionScope | ProtoOAClientPermissionScope | Optional | Token permission scope (`SCOPE_VIEW` / `SCOPE_TRADE`). |
| ctidTraderAccount | RepeatedField<ProtoOACtidTraderAccount> | Repeated | Authorized account list. |

### ProtoOAGetCtidProfileByTokenReq

Purpose: Get the trader profile using an access token (subject to GDPR restrictions).  

| Field | Type | Label | Official description (paraphrased) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | Optional | Payload type. |
| accessToken | string | Required | Access token used for account access. |

### ProtoOAGetCtidProfileByTokenRes

Purpose: Response to `ProtoOAGetCtidProfileByTokenReq`.  

| Field | Type | Label | Official description (paraphrased) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | Optional | Payload type. |
| profile | ProtoOACtidProfile | Required | Trader profile. |

### ProtoOARefreshTokenReq

Purpose: Get a new access token using a refresh token.  

| Field | Type | Label | Official description (paraphrased) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | Optional | Payload type. |
| refreshToken | string | Required | Refresh token used to renew the access token. |

### ProtoOARefreshTokenRes

Purpose: Response to `ProtoOARefreshTokenReq` containing a new token set.  

| Field | Type | Label | Official description (paraphrased) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | Optional | Payload type. |
| accessToken | string | Required | New access token. |
| tokenType | string | Required | Token type (`bearer`). |
| expiresIn | int64 | Required | Access token lifetime in seconds. |
| refreshToken | string | Required | New refresh token. |

### ProtoOATraderReq

Purpose: Get trader account data.  

| Field | Type | Label | Official description (paraphrased) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | Optional | Payload type. |
| ctidTraderAccountId | int64 | Required | trading account ID. |

### ProtoOATraderRes

Purpose: Response to `ProtoOATraderReq`.  

| Field | Type | Label | Official description (paraphrased) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | Optional | Payload type. |
| ctidTraderAccountId | int64 | Required | trading account ID. |
| trader | ProtoOATrader | Required | Trader account information. |

### ProtoOATraderUpdatedEvent

Purpose: Event emitted when the trader account is updated on the server side.  

| Field | Type | Label | Official description (paraphrased) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | Optional | Payload type. |
| ctidTraderAccountId | int64 | Required | trading account ID. |
| trader | ProtoOATrader | Required | Trader account information. |

## Model Messages (Account Related)

### ProtoOAClientPermissionScope (ENUM)

| Name | Value | Official description (paraphrased) |
|---|---|---|
| SCOPE_VIEW | 0 | View-only; trading is not allowed. |
| SCOPE_TRADE | 1 | Tradable; all commands are allowed. |

### ProtoOAAccessRights (ENUM)

| Name | Value | Official description (paraphrased) |
|---|---|---|
| FULL_ACCESS | 0 | All trading is allowed. |
| CLOSE_ONLY | 1 | Only closing positions is allowed. |
| NO_TRADING | 2 | view-only. |
| NO_LOGIN | 3 | no access rights. |

### ProtoOAAccountType (ENUM)

| Name | Value | Official description (paraphrased) |
|---|---|---|
| HEDGED | 0 | Multiple positions are allowed for the same symbol. |
| NETTED | 1 | Only one position is allowed for the same symbol. |
| SPREAD_BETTING | 2 | Spread betting account type. |

### ProtoOACtidProfile

| Field | Type | Label | Official description (paraphrased) |
|---|---|---|---|
| userId | int64 | Required | Trader user ID (GDPR-restricted; only this field is provided). |

### ProtoOACtidTraderAccount

| Field | Type | Label | Official description (paraphrased) |
|---|---|---|---|
| ctidTraderAccountId | uint64 | Required | Unique trading account ID. |
| isLive | bool | Optional | Whether this is a live account; if so, use the live host. |
| traderLogin | int64 | Optional | Trading login ID shown in the UI. |
| lastClosingDealTimestamp | int64 | Optional | Timestamp of the last closing deal in milliseconds. |
| lastBalanceUpdateTimestamp | int64 | Optional | Timestamp of the last balance update in milliseconds. |
| brokerTitleShort | string | Optional | Short broker title shown in the UI. |

### ProtoOALimitedRiskMarginCalculationStrategy (ENUM)

| Name | Value | Official description (paraphrased) |
|---|---|---|
| ACCORDING_TO_LEVERAGE | 0 | Calculated according to leverage. |
| ACCORDING_TO_GSL | 1 | Calculated according to guaranteed stop loss. |
| ACCORDING_TO_GSL_AND_LEVERAGE | 2 | Calculated according to guaranteed stop loss and leverage. |

### ProtoOAStopOutStrategy (ENUM)

| Name | Value | Official description (paraphrased) |
|---|---|---|
| MOST_MARGIN_USED_FIRST | 0 | Close the position using the most margin first. |
| MOST_LOSING_FIRST | 1 | Close the most losing position first. |

### ProtoOATotalMarginCalculationType (ENUM)

| Name | Value | Official description (paraphrased) |
|---|---|---|
| MAX | 0 | MAX. |
| SUM | 1 | SUM. |
| NET | 2 | NET. |

### ProtoOATrader

| Field | Type | Label | Official description (paraphrased) |
|---|---|---|---|
| ctidTraderAccountId | int64 | Required | Trading account ID used to match the response. |
| balance | int64 | Required | Current account balance. |
| balanceVersion | int64 | Optional | Balance version number, incremented on balance changes. |
| managerBonus | int64 | Optional | Bonus amount provided by the broker. |
| ibBonus | int64 | Optional | IB bonus amount. |
| nonWithdrawableBonus | int64 | Optional | Non-withdrawable bonus amount. |
| accessRights | ProtoOAAccessRights | Optional | Account access rights. |
| depositAssetId | int64 | Required | Account deposit asset. |
| swapFree | bool | Optional | Whether this is an Islamic (swap-free) account. |
| leverageInCents | uint32 | Optional | Leverage, where 1:50 is represented as 5000. |
| totalMarginCalculationType | ProtoOATotalMarginCalculationType | Optional | Account margin calculation mode. |
| maxLeverage | uint32 | Optional | Maximum allowed leverage. |
| frenchRisk | bool | Optional | Whether this is an AMF-compliant account. |
| traderLogin | int64 | Optional | Trading login ID, unique on the server. |
| accountType | ProtoOAAccountType | Optional | Account type (HEDGED/NETTED/...). |
| brokerName | string | Optional | White-label broker name assigned by the broker. |
| registrationTimestamp | int64 | Optional | Account registration timestamp in milliseconds. |
| isLimitedRisk | bool | Optional | Whether this is a limited-risk account that requires guaranteed stop loss. |
| limitedRiskMarginCalculationStrategy | ProtoOALimitedRiskMarginCalculationStrategy | Optional | Margin strategy for limited-risk accounts. |
| moneyDigits | uint32 | Optional | Money digits exponent affecting the display of balances and bonuses. |
| fairStopOut | bool | Optional | Whether stop-out closes all positions or only part of them. |
| stopOutStrategy | ProtoOAStopOutStrategy | Optional | Position selection strategy for stop-out. |

## Common Messages

### ProtoErrorRes

| Field | Type | Label | Official description (paraphrased) |
|---|---|---|---|
| payloadType | ProtoPayloadType | Optional | Payload type. |
| errorCode | string | Required | ProtoErrorCode or a custom error code name. |
| description | string | Optional | Error description. |
| maintenanceEndTimestamp | uint64 | Optional | Unix timestamp in milliseconds when maintenance ends. |

### ProtoHeartbeatEvent

| Field | Type | Label | Official description (paraphrased) |
|---|---|---|---|
| payloadType | ProtoPayloadType | Optional | Payload type. |

### ProtoMessage

| Field | Type | Label | Official description (paraphrased) |
|---|---|---|---|
| payloadType | uint32 | Required | ID of the PayloadType or a custom PayloadType. |
| payload | bytes | Optional | Serialized message corresponding to the payloadType. |
| clientMsgId | string | Optional | Client-defined request ID echoed back in the response. |

## Common Model Messages

### ProtoErrorCode (ENUM)

> This enum has many entries; refer to the official Common Model Messages table.

### ProtoPayloadType (ENUM)

> This enum has many entries; refer to the official Common Model Messages table.
