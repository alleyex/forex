# cTrader Open API Full Field List

This document is generated from the official Protobuf definitions. The inferred descriptions are direct name-based translations/guesses and are provided for comprehension only.

## Quick Navigation

- [Open API Messages](#open-api-messages)
- [Open API Model Messages](#open-api-model-messages)
- [Common Messages](#common-messages)
- [Common Model Messages](#common-model-messages)

## How To Use This Document

- Treat this file as a broad field inventory rather than a normative specification.
- Prefer the official cTrader Open API definitions when behavior or semantics are ambiguous.
- Use the account-focused companion document for cleaner auth and account descriptions: [ctrader_openapi_fields_accounts.md](/Users/alleyex/Documents/forex/docs/ctrader_openapi_fields_accounts.md#L1)

## Open API Messages

### ProtoOAAccountAuthReq
Inferred description (name-based): Account authentication request
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | payload type identifier |
| ctidTraderAccountId | int64 | optional | trading account identifier |
| accessToken | string | optional | account access token |

### ProtoOAAccountAuthRes
Inferred description (name-based): Account authentication response
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | payload type identifier |
| ctidTraderAccountId | int64 | optional | trading account identifier |

### ProtoOAAccountDisconnectEvent
Inferred description (name-based): Account disconnect event
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | payload type identifier |
| ctidTraderAccountId | int64 | optional | trading account identifier |

### ProtoOAAccountLogoutReq
Inferred description (name-based): Account logout request
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | payload type identifier |
| ctidTraderAccountId | int64 | optional | trading account identifier |

### ProtoOAAccountLogoutRes
Inferred description (name-based): Account logout response
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | payload type identifier |
| ctidTraderAccountId | int64 | optional | trading account identifier |

### ProtoOAAccountsTokenInvalidatedEvent
Inferred description (name-based): Accounts token invalidated event
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | payload type identifier |
| ctidTraderAccountIds | int64 | repeated | trading account IDs |
| reason | string | optional | reason |

### ProtoOAAmendOrderReq
Inferred description (name-based): Amend order request
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | payload type identifier |
| ctidTraderAccountId | int64 | optional | trading account identifier |
| orderId | int64 | optional | order identifier |
| volume | int64 | optional | volume |
| limitPrice | double | optional | price |
| stopPrice | double | optional | price |
| expirationTimestamp | int64 | optional | timestamp |
| stopLoss | double | optional | loss |
| takeProfit | double | optional | profit |
| slippageInPoints | int32 | optional | slippage in points |
| relativeStopLoss | int64 | optional | stop loss |
| relativeTakeProfit | int64 | optional | take profit |
| guaranteedStopLoss | bool | optional | stop loss |
| trailingStopLoss | bool | optional | stop loss |
| stopTriggerMethod | ProtoOAOrderTriggerMethod | optional | stop trigger method |

### ProtoOAAmendPositionSLTPReq
Inferred description (name-based): Amend position SL/TP request
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | payload type identifier |
| ctidTraderAccountId | int64 | optional | trading account identifier |
| positionId | int64 | optional | position identifier |
| stopLoss | double | optional | loss |
| takeProfit | double | optional | profit |
| guaranteedStopLoss | bool | optional | stop loss |
| trailingStopLoss | bool | optional | stop loss |
| stopLossTriggerMethod | ProtoOAOrderTriggerMethod | optional | stop-loss trigger method |

### ProtoOAApplicationAuthReq
Inferred description (name-based): Application authentication request
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | payload type identifier |
| clientId | string | optional | client identifier |
| clientSecret | string | optional | client secret |

### ProtoOAApplicationAuthRes
Inferred description (name-based): Application authentication response
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | payload type identifier |

### ProtoOAAssetClassListReq
Inferred description (name-based): Asset class list request
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | payload type identifier |
| ctidTraderAccountId | int64 | optional | trading account identifier |

### ProtoOAAssetClassListRes
Inferred description (name-based): Asset class list response
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | payload type identifier |
| ctidTraderAccountId | int64 | optional | trading account identifier |
| assetClass | ProtoOAAssetClass | repeated | asset class entries |

### ProtoOAAssetListReq
Inferred description (name-based): Asset list request
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | payload type identifier |
| ctidTraderAccountId | int64 | optional | trading account identifier |

### ProtoOAAssetListRes
Inferred description (name-based): Asset list response
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | payload type identifier |
| ctidTraderAccountId | int64 | optional | trading account identifier |
| asset | ProtoOAAsset | repeated | asset entries |

### ProtoOACancelOrderReq
Inferred description (name-based): Cancel order request
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | payload type identifier |
| ctidTraderAccountId | int64 | optional | trading account identifier |
| orderId | int64 | optional | order identifier |

### ProtoOACashFlowHistoryListReq
Inferred description (name-based): Cash flow history list request
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | payload type identifier |
| ctidTraderAccountId | int64 | optional | trading account identifier |
| fromTimestamp | int64 | optional | timestamp |
| toTimestamp | int64 | optional | timestamp |

### ProtoOACashFlowHistoryListRes
Inferred description (name-based): Cash flow history list response
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | payload type identifier |
| ctidTraderAccountId | int64 | optional | trading account identifier |
| depositWithdraw | ProtoOADepositWithdraw | repeated | deposit/withdraw entries |

### ProtoOAClientDisconnectEvent
Inferred description (name-based): Client disconnect event
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | payload type identifier |
| reason | string | optional | reason |

### ProtoOAClosePositionReq
Inferred description (name-based): Close position request
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | payload type identifier |
| ctidTraderAccountId | int64 | optional | trading account identifier |
| positionId | int64 | optional | position identifier |
| volume | int64 | optional | volume |

### ProtoOADealListByPositionIdReq
Inferred description (name-based): Deal list by position ID request
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | payload type identifier |
| ctidTraderAccountId | int64 | optional | trading account identifier |
| positionId | int64 | optional | position identifier |
| fromTimestamp | int64 | optional | timestamp |
| toTimestamp | int64 | optional | timestamp |

### ProtoOADealListByPositionIdRes
Inferred description (name-based): Deal list by position ID response
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | payload type identifier |
| ctidTraderAccountId | int64 | optional | trading account identifier |
| deal | ProtoOADeal | repeated | deal entries |
| hasMore | int64 | optional | has-more flag |

### ProtoOADealListReq
Inferred description (name-based): Deal list request
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | payload type identifier |
| ctidTraderAccountId | int64 | optional | trading account identifier |
| fromTimestamp | int64 | optional | timestamp |
| toTimestamp | int64 | optional | timestamp |
| maxRows | int32 | optional | maximum row count |

### ProtoOADealListRes
Inferred description (name-based): Deal list response
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | payload type identifier |
| ctidTraderAccountId | int64 | optional | trading account identifier |
| deal | ProtoOADeal | repeated | deal entries |
| hasMore | bool | optional | has-more flag |

### ProtoOADealOffsetListReq
Inferred description (name-based): Deal offset list request
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | payload type identifier |
| ctidTraderAccountId | int64 | optional | trading account identifier |
| dealId | int64 | optional | deal identifier |

### ProtoOADealOffsetListRes
Inferred description (name-based): Deal offset list response
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | payload type identifier |
| ctidTraderAccountId | int64 | optional | trading account identifier |
| offsetBy | ProtoOADealOffset | repeated | offset-by entries |
| offsetting | ProtoOADealOffset | repeated | offsetting |

### ProtoOADepthEvent
Inferred description (name-based): Depth event
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | payload type identifier |
| ctidTraderAccountId | int64 | optional | trading account identifier |
| symbolId | uint64 | optional | symbol identifier |
| newQuotes | ProtoOADepthQuote | repeated | new quote entries |
| deletedQuotes | uint64 | repeated | deleted quote identifiers |

### ProtoOAErrorRes
Inferred description (name-based): Error response
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | payload type identifier |
| ctidTraderAccountId | int64 | optional | trading account identifier |
| errorCode | string | optional | error code |
| description | string | optional | text description |
| maintenanceEndTimestamp | int64 | optional | end timestamp |

### ProtoOAExecutionEvent
Inferred description (name-based): Execution event
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | payload type identifier |
| ctidTraderAccountId | int64 | optional | trading account identifier |
| executionType | ProtoOAExecutionType | optional | execution type |
| position | ProtoOAPosition | optional | position |
| order | ProtoOAOrder | optional | order |
| deal | ProtoOADeal | optional | deal |
| bonusDepositWithdraw | ProtoOABonusDepositWithdraw | optional | bonus deposit/withdraw details |
| depositWithdraw | ProtoOADepositWithdraw | optional | deposit/withdraw details |
| errorCode | string | optional | error code |
| isServerEvent | bool | optional | server-event flag |

### ProtoOAExpectedMarginReq
Inferred description (name-based): Expected margin request
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | payload type identifier |
| ctidTraderAccountId | int64 | optional | trading account identifier |
| symbolId | int64 | optional | symbol identifier |
| volume | int64 | repeated | volume |

### ProtoOAExpectedMarginRes
Inferred description (name-based): Expected margin response
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | payload type identifier |
| ctidTraderAccountId | int64 | optional | trading account identifier |
| margin | ProtoOAExpectedMargin | repeated | margin |
| moneyDigits | uint32 | optional | money digits precision |

### ProtoOAGetAccountListByAccessTokenReq
Inferred description (name-based): Get account list by access token request
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | payload type identifier |
| accessToken | string | optional | account access token |

### ProtoOAGetAccountListByAccessTokenRes
Inferred description (name-based): Get account list by access token response
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | payload type identifier |
| accessToken | string | optional | account access token |
| permissionScope | ProtoOAClientPermissionScope | optional | permission scope |
| ctidTraderAccount | ProtoOACtidTraderAccount | repeated | trading account entries |

### ProtoOAGetCtidProfileByTokenReq
Inferred description (name-based): Get CTID profile by token request
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | payload type identifier |
| accessToken | string | optional | account access token |

### ProtoOAGetCtidProfileByTokenRes
Inferred description (name-based): Get CTID profile by token response
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | payload type identifier |
| profile | ProtoOACtidProfile | optional | CTID profile |

### ProtoOAGetDynamicLeverageByIDReq
Inferred description (name-based): Get dynamic leverage by ID request
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | payload type identifier |
| ctidTraderAccountId | int64 | optional | trading account identifier |
| leverageId | int64 | optional | leverage tier identifier |

### ProtoOAGetDynamicLeverageByIDRes
Inferred description (name-based): Get dynamic leverage by ID response
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | payload type identifier |
| ctidTraderAccountId | int64 | optional | trading account identifier |
| leverage | ProtoOADynamicLeverage | optional | leverage |

### ProtoOAGetPositionUnrealizedPnLReq
Inferred description (name-based): Get position unrealized pn l request
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | payload type identifier |
| ctidTraderAccountId | int64 | optional | trading account identifier |

### ProtoOAGetPositionUnrealizedPnLRes
Inferred description (name-based): Get position unrealized pn l response
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | payload type identifier |
| ctidTraderAccountId | int64 | optional | trading account identifier |
| positionUnrealizedPnL | ProtoOAPositionUnrealizedPnL | repeated | UnrealizedPnL |
| moneyDigits | uint32 | optional | money digits precision |

### ProtoOAGetTickDataReq
Inferred description (name-based): Get tick data request
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | payload type identifier |
| ctidTraderAccountId | int64 | optional | trading account identifier |
| symbolId | int64 | optional | symbol identifier |
| type | ProtoOAQuoteType | optional | quote type |
| fromTimestamp | int64 | optional | timestamp |
| toTimestamp | int64 | optional | timestamp |

### ProtoOAGetTickDataRes
Inferred description (name-based): Get tick data response
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | payload type identifier |
| ctidTraderAccountId | int64 | optional | trading account identifier |
| tickData | ProtoOATickData | repeated | Data |
| hasMore | bool | optional | has-more flag |

### ProtoOAGetTrendbarsReq
Inferred description (name-based): Get trendbars request
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | payload type identifier |
| ctidTraderAccountId | int64 | optional | trading account identifier |
| fromTimestamp | int64 | optional | timestamp |
| toTimestamp | int64 | optional | timestamp |
| period | ProtoOATrendbarPeriod | optional | period |
| symbolId | int64 | optional | symbol identifier |
| count | uint32 | optional | count |

### ProtoOAGetTrendbarsRes
Inferred description (name-based): Get trendbars response
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | payload type identifier |
| ctidTraderAccountId | int64 | optional | trading account identifier |
| period | ProtoOATrendbarPeriod | optional | period |
| timestamp | int64 | optional | timestamp |
| trendbar | ProtoOATrendbar | repeated | trendbar |
| symbolId | int64 | optional | symbol identifier |

### ProtoOAMarginCallListReq
Inferred description (name-based): Margin call list request
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | payload type identifier |
| ctidTraderAccountId | int64 | optional | trading account identifier |

### ProtoOAMarginCallListRes
Inferred description (name-based): Margin call list response
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | payload type identifier |
| marginCall | ProtoOAMarginCall | repeated | Call |

### ProtoOAMarginCallTriggerEvent
Inferred description (name-based): Margin call trigger event
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | payload type identifier |
| ctidTraderAccountId | int64 | optional | trading account identifier |
| marginCall | ProtoOAMarginCall | optional | Call |

### ProtoOAMarginCallUpdateEvent
Inferred description (name-based): Margin call update event
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | payload type identifier |
| ctidTraderAccountId | int64 | optional | trading account identifier |
| marginCall | ProtoOAMarginCall | optional | Call |

### ProtoOAMarginCallUpdateReq
Inferred description (name-based): Margin call update request
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | payload type identifier |
| ctidTraderAccountId | int64 | optional | trading account identifier |
| marginCall | ProtoOAMarginCall | optional | Call |

### ProtoOAMarginCallUpdateRes
Inferred description (name-based): Margin call update response
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | payload type identifier |

### ProtoOAMarginChangedEvent
Inferred description (name-based): Margin changed event
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | payload type identifier |
| ctidTraderAccountId | int64 | optional | trading account identifier |
| positionId | uint64 | optional | position identifier |
| usedMargin | uint64 | optional | margin |
| moneyDigits | uint32 | optional | money digits precision |

### ProtoOANewOrderReq
Inferred description (name-based): New order request
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | payload type identifier |
| ctidTraderAccountId | int64 | optional | trading account identifier |
| symbolId | int64 | optional | symbol identifier |
| orderType | ProtoOAOrderType | optional | order type |
| tradeSide | ProtoOATradeSide | optional | side |
| volume | int64 | optional | volume |
| limitPrice | double | optional | price |
| stopPrice | double | optional | price |
| timeInForce | ProtoOATimeInForce | optional | InForce |
| expirationTimestamp | int64 | optional | timestamp |
| stopLoss | double | optional | loss |
| takeProfit | double | optional | profit |
| comment | string | optional | comment |
| baseSlippagePrice | double | optional | slippage price |
| slippageInPoints | int32 | optional | slippage in points |
| label | string | optional | label |
| positionId | int64 | optional | position identifier |
| clientOrderId | string | optional | orderID |
| relativeStopLoss | int64 | optional | stop loss |
| relativeTakeProfit | int64 | optional | take profit |
| guaranteedStopLoss | bool | optional | stop loss |
| trailingStopLoss | bool | optional | stop loss |
| stopTriggerMethod | ProtoOAOrderTriggerMethod | optional | stop trigger method |

### ProtoOAOrderDetailsReq
Inferred description (name-based): Order details request
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | payload type identifier |
| ctidTraderAccountId | int64 | optional | trading account identifier |
| orderId | int64 | optional | order identifier |

### ProtoOAOrderDetailsRes
Inferred description (name-based): Order details response
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | payload type identifier |
| ctidTraderAccountId | int64 | optional | trading account identifier |
| order | ProtoOAOrder | optional | order |
| deal | ProtoOADeal | repeated | deal entries |

### ProtoOAOrderErrorEvent
Inferred description (name-based): Order error event
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | payload type identifier |
| ctidTraderAccountId | int64 | optional | trading account identifier |
| errorCode | string | optional | error code |
| orderId | int64 | optional | order identifier |
| positionId | int64 | optional | position identifier |
| description | string | optional | text description |

### ProtoOAOrderListByPositionIdReq
Inferred description (name-based): Order list by position ID request
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | payload type identifier |
| ctidTraderAccountId | int64 | optional | trading account identifier |
| positionId | int64 | optional | position identifier |
| fromTimestamp | int64 | optional | timestamp |
| toTimestamp | int64 | optional | timestamp |

### ProtoOAOrderListByPositionIdRes
Inferred description (name-based): Order list by position ID response
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | payload type identifier |
| ctidTraderAccountId | int64 | optional | trading account identifier |
| order | ProtoOAOrder | repeated | order |
| hasMore | bool | optional | has-more flag |

### ProtoOAOrderListReq
Inferred description (name-based): Order list request
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | payload type identifier |
| ctidTraderAccountId | int64 | optional | trading account identifier |
| fromTimestamp | int64 | optional | timestamp |
| toTimestamp | int64 | optional | timestamp |

### ProtoOAOrderListRes
Inferred description (name-based): Order list response
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | payload type identifier |
| ctidTraderAccountId | int64 | optional | trading account identifier |
| order | ProtoOAOrder | repeated | order |
| hasMore | bool | optional | has-more flag |

### ProtoOAReconcileReq
Inferred description (name-based): Reconcile request
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | payload type identifier |
| ctidTraderAccountId | int64 | optional | trading account identifier |

### ProtoOAReconcileRes
Inferred description (name-based): Reconcile response
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | payload type identifier |
| ctidTraderAccountId | int64 | optional | trading account identifier |
| position | ProtoOAPosition | repeated | position |
| order | ProtoOAOrder | repeated | order |

### ProtoOARefreshTokenReq
Inferred description (name-based): Refresh token request
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | payload type identifier |
| refreshToken | string | optional | refresh token |

### ProtoOARefreshTokenRes
Inferred description (name-based): Refresh token response
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | payload type identifier |
| accessToken | string | optional | account access token |
| tokenType | string | optional | token type |
| expiresIn | int64 | optional | In |
| refreshToken | string | optional | refresh token |

### ProtoOASpotEvent
Inferred description (name-based): Spot event
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | payload type identifier |
| ctidTraderAccountId | int64 | optional | trading account identifier |
| symbolId | int64 | optional | symbol identifier |
| bid | uint64 | optional | bid |
| ask | uint64 | optional | ask |
| trendbar | ProtoOATrendbar | repeated | trendbar |
| sessionClose | uint64 | optional | close |
| timestamp | int64 | optional | timestamp |

### ProtoOASubscribeDepthQuotesReq
Inferred description (name-based): Subscribe depth quotes request
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | payload type identifier |
| ctidTraderAccountId | int64 | optional | trading account identifier |
| symbolId | int64 | repeated | symbol identifiers |

### ProtoOASubscribeDepthQuotesRes
Inferred description (name-based): Subscribe depth quotes response
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | payload type identifier |
| ctidTraderAccountId | int64 | optional | trading account identifier |

### ProtoOASubscribeLiveTrendbarReq
Inferred description (name-based): Subscribe live trendbar request
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | payload type identifier |
| ctidTraderAccountId | int64 | optional | trading account identifier |
| period | ProtoOATrendbarPeriod | optional | period |
| symbolId | int64 | optional | symbol identifier |

### ProtoOASubscribeLiveTrendbarRes
Inferred description (name-based): Subscribe live trendbar response
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | payload type identifier |
| ctidTraderAccountId | int64 | optional | trading account identifier |

### ProtoOASubscribeSpotsReq
Inferred description (name-based): Subscribe spots request
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | payload type identifier |
| ctidTraderAccountId | int64 | optional | trading account identifier |
| symbolId | int64 | repeated | symbol identifiers |
| subscribeToSpotTimestamp | bool | optional | Tospot quotetimestamp |

### ProtoOASubscribeSpotsRes
Inferred description (name-based): Subscribe spots response
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | payload type identifier |
| ctidTraderAccountId | int64 | optional | trading account identifier |

### ProtoOASymbolByIdReq
Inferred description (name-based): Symbol by ID request
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | payload type identifier |
| ctidTraderAccountId | int64 | optional | trading account identifier |
| symbolId | int64 | repeated | symbol identifiers |

### ProtoOASymbolByIdRes
Inferred description (name-based): Symbol by ID response
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | payload type identifier |
| ctidTraderAccountId | int64 | optional | trading account identifier |
| symbol | ProtoOASymbol | repeated | symbol |
| archivedSymbol | ProtoOAArchivedSymbol | repeated | symbol |

### ProtoOASymbolCategoryListReq
Inferred description (name-based): Symbol category list request
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | payload type identifier |
| ctidTraderAccountId | int64 | optional | trading account identifier |

### ProtoOASymbolCategoryListRes
Inferred description (name-based): Symbol category list response
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | payload type identifier |
| ctidTraderAccountId | int64 | optional | trading account identifier |
| symbolCategory | ProtoOASymbolCategory | repeated | Category |

### ProtoOASymbolChangedEvent
Inferred description (name-based): Symbol changed event
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | payload type identifier |
| ctidTraderAccountId | int64 | optional | trading account identifier |
| symbolId | int64 | repeated | symbol identifiers |

### ProtoOASymbolsForConversionReq
Inferred description (name-based): Symbols for conversion request
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | payload type identifier |
| ctidTraderAccountId | int64 | optional | trading account identifier |
| firstAssetId | int64 | optional | asset ID |
| lastAssetId | int64 | optional | asset ID |

### ProtoOASymbolsForConversionRes
Inferred description (name-based): Symbols for conversion response
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | payload type identifier |
| ctidTraderAccountId | int64 | optional | trading account identifier |
| symbol | ProtoOALightSymbol | repeated | symbol |

### ProtoOASymbolsListReq
Inferred description (name-based): Symbols list request
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | payload type identifier |
| ctidTraderAccountId | int64 | optional | trading account identifier |
| includeArchivedSymbols | bool | optional | Archivedsymbol |

### ProtoOASymbolsListRes
Inferred description (name-based): Symbols list response
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | payload type identifier |
| ctidTraderAccountId | int64 | optional | trading account identifier |
| symbol | ProtoOALightSymbol | repeated | symbol |
| archivedSymbol | ProtoOAArchivedSymbol | repeated | symbol |

### ProtoOATraderReq
Inferred description (name-based): Trader request
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | payload type identifier |
| ctidTraderAccountId | int64 | optional | trading account identifier |

### ProtoOATraderRes
Inferred description (name-based): Trader response
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | payload type identifier |
| ctidTraderAccountId | int64 | optional | trading account identifier |
| trader | ProtoOATrader | optional | trader |

### ProtoOATraderUpdatedEvent
Inferred description (name-based): Trader updated event
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | payload type identifier |
| ctidTraderAccountId | int64 | optional | trading account identifier |
| trader | ProtoOATrader | optional | trader |

### ProtoOATrailingSLChangedEvent
Inferred description (name-based): Trailing sl changed event
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | payload type identifier |
| ctidTraderAccountId | int64 | optional | trading account identifier |
| positionId | int64 | optional | position identifier |
| orderId | int64 | optional | order identifier |
| stopPrice | double | optional | price |
| utcLastUpdateTimestamp | int64 | optional | last update timestamp |

### ProtoOAUnsubscribeDepthQuotesReq
Inferred description (name-based): Unsubscribe depth quotes request
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | payload type identifier |
| ctidTraderAccountId | int64 | optional | trading account identifier |
| symbolId | int64 | repeated | symbol identifiers |

### ProtoOAUnsubscribeDepthQuotesRes
Inferred description (name-based): Unsubscribe depth quotes response
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | payload type identifier |
| ctidTraderAccountId | int64 | optional | trading account identifier |

### ProtoOAUnsubscribeLiveTrendbarReq
Inferred description (name-based): Unsubscribe live trendbar request
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | payload type identifier |
| ctidTraderAccountId | int64 | optional | trading account identifier |
| period | ProtoOATrendbarPeriod | optional | period |
| symbolId | int64 | optional | symbol identifier |

### ProtoOAUnsubscribeLiveTrendbarRes
Inferred description (name-based): Unsubscribe live trendbar response
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | payload type identifier |
| ctidTraderAccountId | int64 | optional | trading account identifier |

### ProtoOAUnsubscribeSpotsReq
Inferred description (name-based): Unsubscribe spots request
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | payload type identifier |
| ctidTraderAccountId | int64 | optional | trading account identifier |
| symbolId | int64 | repeated | symbol identifiers |

### ProtoOAUnsubscribeSpotsRes
Inferred description (name-based): Unsubscribe spots response
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | payload type identifier |
| ctidTraderAccountId | int64 | optional | trading account identifier |

### ProtoOAVersionReq
Inferred description (name-based): Version request
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | payload type identifier |

### ProtoOAVersionRes
Inferred description (name-based): Version response
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | payload type identifier |
| version | string | optional | version string |

## Open API Model Messages

### ProtoOAArchivedSymbol
Inferred description (name-based): Archived symbol
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| symbolId | int64 | optional | symbol identifier |
| name | string | optional | name |
| utcLastUpdateTimestamp | int64 | optional | last update timestamp |
| description | string | optional | text description |

### ProtoOAAsset
Inferred description (name-based): Asset
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| assetId | int64 | optional | asset identifier |
| name | string | optional | name |
| displayName | string | optional | display name |
| digits | int32 | optional | digits |

### ProtoOAAssetClass
Inferred description (name-based): Asset class
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| id | int64 | optional | id |
| name | string | optional | name |

### ProtoOABonusDepositWithdraw
Inferred description (name-based): Bonus deposit withdraw
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| operationType | ProtoOAChangeBonusType | optional | bonus operation type |
| bonusHistoryId | int64 | optional | history ID |
| managerBonus | int64 | optional | Bonus |
| managerDelta | int64 | optional | Delta |
| ibBonus | int64 | optional | Bonus |
| ibDelta | int64 | optional | Delta |
| changeBonusTimestamp | int64 | optional | bonus timestamp |
| externalNote | string | optional | Note |
| introducingBrokerId | int64 | optional | BrokerID |
| moneyDigits | uint32 | optional | money digits precision |

### ProtoOAClosePositionDetail
Inferred description (name-based): Close position detail
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| entryPrice | double | optional | price |
| grossProfit | int64 | optional | profit |
| swap | int64 | optional | swap |
| commission | int64 | optional | commission |
| balance | int64 | optional | balance |
| quoteToDepositConversionRate | double | optional | ToDepositConversionRate |
| closedVolume | int64 | optional | volume |
| balanceVersion | int64 | optional | Version |
| moneyDigits | uint32 | optional | money digits precision |
| pnlConversionFee | int64 | optional | conversion fee |

### ProtoOACtidProfile
Inferred description (name-based): CTID profile
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| userId | int64 | optional | user identifier |

### ProtoOACtidTraderAccount
Inferred description (name-based): CTID trader account
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| ctidTraderAccountId | uint64 | optional | trading account identifier |
| isLive | bool | optional | Live |
| traderLogin | int64 | optional | trader login identifier |
| lastClosingDealTimestamp | int64 | optional | closing deal timestamp |
| lastBalanceUpdateTimestamp | int64 | optional | balance update timestamp |

### ProtoOADeal
Inferred description (name-based): Deal
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| dealId | int64 | optional | deal identifier |
| orderId | int64 | optional | order identifier |
| positionId | int64 | optional | position identifier |
| volume | int64 | optional | volume |
| filledVolume | int64 | optional | volume |
| symbolId | int64 | optional | symbol identifier |
| createTimestamp | int64 | optional | timestamp |
| executionTimestamp | int64 | optional | timestamp |
| utcLastUpdateTimestamp | int64 | optional | last update timestamp |
| executionPrice | double | optional | price |
| tradeSide | ProtoOATradeSide | optional | side |
| dealStatus | ProtoOADealStatus | optional | status |
| marginRate | double | optional | Rate |
| commission | int64 | optional | commission |
| baseToUsdConversionRate | double | optional | ToUsdConversionRate |
| closePositionDetail | ProtoOAClosePositionDetail | optional | position detail |
| moneyDigits | uint32 | optional | money digits precision |

### ProtoOADealOffset
Inferred description (name-based): Deal offset
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| dealId | int64 | optional | deal identifier |
| volume | int64 | optional | volume |
| executionTimestamp | int64 | optional | timestamp |
| executionPrice | double | optional | price |

### ProtoOADepositWithdraw
Inferred description (name-based): Deposit withdraw
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| operationType | ProtoOAChangeBalanceType | optional | balance operation type |
| balanceHistoryId | int64 | optional | history ID |
| balance | int64 | optional | balance |
| delta | int64 | optional | delta |
| changeBalanceTimestamp | int64 | optional | balance timestamp |
| externalNote | string | optional | Note |
| balanceVersion | int64 | optional | Version |
| equity | int64 | optional | equity |
| moneyDigits | uint32 | optional | money digits precision |

### ProtoOADepthQuote
Inferred description (name-based): Depth quote
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| id | uint64 | optional | id |
| size | uint64 | optional | size |
| bid | uint64 | optional | bid |
| ask | uint64 | optional | ask |

### ProtoOADynamicLeverage
Inferred description (name-based): Dynamic leverage
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| leverageId | int64 | optional | leverage tier identifier |
| tiers | ProtoOADynamicLeverageTier | repeated | tiers |

### ProtoOADynamicLeverageTier
Inferred description (name-based): Dynamic leverage tier
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| volume | int64 | optional | volume |
| leverage | int64 | optional | leverage |

### ProtoOAExpectedMargin
Inferred description (name-based): Expected margin
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| volume | int64 | optional | volume |
| buyMargin | int64 | optional | margin |
| sellMargin | int64 | optional | margin |

### ProtoOAHoliday
Inferred description (name-based): Holiday
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| holidayId | int64 | optional | holiday identifier |
| name | string | optional | name |
| description | string | optional | text description |
| scheduleTimeZone | string | optional | time zone |
| holidayDate | int64 | optional | Date |
| isRecurring | bool | optional | Recurring |
| startSecond | int32 | optional | Second |
| endSecond | int32 | optional | Second |

### ProtoOAInterval
Inferred description (name-based): Interval
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| startSecond | uint32 | optional | Second |
| endSecond | uint32 | optional | Second |

### ProtoOALightSymbol
Inferred description (name-based): Light symbol
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| symbolId | int64 | optional | symbol identifier |
| symbolName | string | optional | symbol name |
| enabled | bool | optional | enabled |
| baseAssetId | int64 | optional | asset ID |
| quoteAssetId | int64 | optional | asset ID |
| symbolCategoryId | int64 | optional | CategoryID |
| description | string | optional | text description |

### ProtoOAMarginCall
Inferred description (name-based): Margin call
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| marginCallType | ProtoOANotificationType | optional | Calltype |
| marginLevelThreshold | double | optional | LevelThreshold |
| utcLastUpdateTimestamp | int64 | optional | last update timestamp |

### ProtoOAOrder
Inferred description (name-based): Order
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| orderId | int64 | optional | order identifier |
| tradeData | ProtoOATradeData | optional | Data |
| orderType | ProtoOAOrderType | optional | order type |
| orderStatus | ProtoOAOrderStatus | optional | status |
| expirationTimestamp | int64 | optional | timestamp |
| executionPrice | double | optional | price |
| executedVolume | int64 | optional | volume |
| utcLastUpdateTimestamp | int64 | optional | last update timestamp |
| baseSlippagePrice | double | optional | slippage price |
| slippageInPoints | int64 | optional | InPoints |
| closingOrder | bool | optional | order |
| limitPrice | double | optional | price |
| stopPrice | double | optional | price |
| stopLoss | double | optional | loss |
| takeProfit | double | optional | profit |
| clientOrderId | string | optional | orderID |
| timeInForce | ProtoOATimeInForce | optional | InForce |
| positionId | int64 | optional | position identifier |
| relativeStopLoss | int64 | optional | stop loss |
| relativeTakeProfit | int64 | optional | take profit |
| isStopOut | bool | optional | stop-out |
| trailingStopLoss | bool | optional | stop loss |
| stopTriggerMethod | ProtoOAOrderTriggerMethod | optional | stop trigger method |

### ProtoOAPosition
Inferred description (name-based): Position
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| positionId | int64 | optional | position identifier |
| tradeData | ProtoOATradeData | optional | Data |
| positionStatus | ProtoOAPositionStatus | optional | status |
| swap | int64 | optional | swap |
| price | double | optional | price |
| stopLoss | double | optional | loss |
| takeProfit | double | optional | profit |
| utcLastUpdateTimestamp | int64 | optional | last update timestamp |
| commission | int64 | optional | commission |
| marginRate | double | optional | Rate |
| mirroringCommission | int64 | optional | Commission |
| guaranteedStopLoss | bool | optional | stop loss |
| usedMargin | uint64 | optional | margin |
| stopLossTriggerMethod | ProtoOAOrderTriggerMethod | optional | stop-loss trigger method |
| moneyDigits | uint32 | optional | money digits precision |
| trailingStopLoss | bool | optional | stop loss |

### ProtoOAPositionUnrealizedPnL
Inferred description (name-based): Position unrealized pn l
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| positionId | int64 | optional | position identifier |
| grossUnrealizedPnL | int64 | optional | UnrealizedPnL |
| netUnrealizedPnL | int32 | optional | UnrealizedPnL |

### ProtoOASymbol
Inferred description (name-based): Symbol
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| symbolId | int64 | optional | symbol identifier |
| digits | int32 | optional | digits |
| pipPosition | int32 | optional | position |
| enableShortSelling | bool | optional | ShortSelling |
| guaranteedStopLoss | bool | optional | stop loss |
| swapRollover3Days | ProtoOADayOfWeek | optional | Rollover3Days |
| swapLong | double | optional | Long |
| swapShort | double | optional | Short |
| maxVolume | int64 | optional | volume |
| minVolume | int64 | optional | volume |
| stepVolume | int64 | optional | volume |
| maxExposure | uint64 | optional | Exposure |
| schedule | ProtoOAInterval | repeated | schedule |
| commission | int64 | optional | commission |
| commissionType | ProtoOACommissionType | optional | commission type |
| slDistance | uint32 | optional | Distance |
| tpDistance | uint32 | optional | Distance |
| gslDistance | uint32 | optional | Distance |
| gslCharge | int64 | optional | Charge |
| distanceSetIn | ProtoOASymbolDistanceType | optional | SetIn |
| minCommission | int64 | optional | Commission |
| minCommissionType | ProtoOAMinCommissionType | optional | commission type |
| minCommissionAsset | string | optional | commission asset |
| rolloverCommission | int64 | optional | Commission |
| skipRolloverDays | int32 | optional | RolloverDays |
| scheduleTimeZone | string | optional | time zone |
| tradingMode | ProtoOATradingMode | optional | Mode |
| rolloverCommission3Days | ProtoOADayOfWeek | optional | Commission3Days |
| swapCalculationType | ProtoOASwapCalculationType | optional | calculation type |
| lotSize | int64 | optional | Size |
| preciseTradingCommissionRate | int64 | optional | TradingCommissionRate |
| preciseMinCommission | int64 | optional | minimum commission |
| holiday | ProtoOAHoliday | repeated | holiday |
| pnlConversionFeeRate | int32 | optional | conversion fee rate |
| leverageId | int64 | optional | leverage tier identifier |
| swapPeriod | int32 | optional | period |
| swapTime | int32 | optional | time |
| skipSWAPPeriods | int32 | optional | SWAPPeriods |
| chargeSwapAtWeekends | bool | optional | SwapAtWeekends |

### ProtoOASymbolCategory
Inferred description (name-based): Symbol category
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| id | int64 | optional | id |
| assetClassId | int64 | optional | ClassID |
| name | string | optional | name |

### ProtoOATickData
Inferred description (name-based): Tick data
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| timestamp | int64 | optional | timestamp |
| tick | int64 | optional | tick |

### ProtoOATradeData
Inferred description (name-based): Trade data
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| symbolId | int64 | optional | symbol identifier |
| volume | int64 | optional | volume |
| tradeSide | ProtoOATradeSide | optional | side |
| openTimestamp | int64 | optional | timestamp |
| label | string | optional | label |
| guaranteedStopLoss | bool | optional | stop loss |
| comment | string | optional | comment |

### ProtoOATrader
Inferred description (name-based): Trader
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| ctidTraderAccountId | int64 | optional | trading account identifier |
| balance | int64 | optional | balance |
| balanceVersion | int64 | optional | Version |
| managerBonus | int64 | optional | Bonus |
| ibBonus | int64 | optional | Bonus |
| nonWithdrawableBonus | int64 | optional | WithdrawableBonus |
| accessRights | ProtoOAAccessRights | optional | access rights |
| depositAssetId | int64 | optional | asset ID |
| swapFree | bool | optional | swap-free flag |
| leverageInCents | uint32 | optional | leverage value in cents |
| totalMarginCalculationType | ProtoOATotalMarginCalculationType | optional | margin calculation type |
| maxLeverage | uint32 | optional | leverage |
| frenchRisk | bool | optional | risk |
| traderLogin | int64 | optional | trader login identifier |
| accountType | ProtoOAAccountType | optional | account type |
| brokerName | string | optional | broker name |
| registrationTimestamp | int64 | optional | timestamp |
| isLimitedRisk | bool | optional | limited-risk flag |
| limitedRiskMarginCalculationStrategy | ProtoOALimitedRiskMarginCalculationStrategy | optional | risk margin calculation strategy |
| moneyDigits | uint32 | optional | money digits precision |

### ProtoOATrendbar
Inferred description (name-based): Trendbar
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| volume | int64 | optional | volume |
| period | ProtoOATrendbarPeriod | optional | period |
| low | int64 | optional | low |
| deltaOpen | uint64 | optional | open |
| deltaClose | uint64 | optional | close |
| deltaHigh | uint64 | optional | high |
| utcTimestampInMinutes | uint32 | optional | timestamp in minutes |

### ProtoOAAccessRights
Inferred description (name-based): Access rights
| Name | Value | Inferred description (name-based) |
|---|---|---|
| FULL_ACCESS | 0 | Enum value `FULL_ACCESS`. |
| CLOSE_ONLY | 1 | Enum value `CLOSE_ONLY`. |
| NO_TRADING | 2 | Enum value `NO_TRADING`. |
| NO_LOGIN | 3 | Enum value `NO_LOGIN`. |

### ProtoOAAccountType
Inferred description (name-based): Account type
| Name | Value | Inferred description (name-based) |
|---|---|---|
| HEDGED | 0 | Enum value `HEDGED`. |
| NETTED | 1 | Enum value `NETTED`. |
| SPREAD_BETTING | 2 | Enum value `SPREAD_BETTING`. |

### ProtoOAChangeBalanceType
Inferred description (name-based): Change balance type
| Name | Value | Inferred description (name-based) |
|---|---|---|
| BALANCE_DEPOSIT | 0 | Enum value `BALANCE_DEPOSIT`. |
| BALANCE_WITHDRAW | 1 | Enum value `BALANCE_WITHDRAW`. |
| BALANCE_DEPOSIT_STRATEGY_COMMISSION_INNER | 3 | Enum value `BALANCE_DEPOSIT_STRATEGY_COMMISSION_INNER`. |
| BALANCE_WITHDRAW_STRATEGY_COMMISSION_INNER | 4 | Enum value `BALANCE_WITHDRAW_STRATEGY_COMMISSION_INNER`. |
| BALANCE_DEPOSIT_IB_COMMISSIONS | 5 | Enum value `BALANCE_DEPOSIT_IB_COMMISSIONS`. |
| BALANCE_WITHDRAW_IB_SHARED_PERCENTAGE | 6 | Enum value `BALANCE_WITHDRAW_IB_SHARED_PERCENTAGE`. |
| BALANCE_DEPOSIT_IB_SHARED_PERCENTAGE_FROM_SUB_IB | 7 | Enum value `BALANCE_DEPOSIT_IB_SHARED_PERCENTAGE_FROM_SUB_IB`. |
| BALANCE_DEPOSIT_IB_SHARED_PERCENTAGE_FROM_BROKER | 8 | Enum value `BALANCE_DEPOSIT_IB_SHARED_PERCENTAGE_FROM_BROKER`. |
| BALANCE_DEPOSIT_REBATE | 9 | Enum value `BALANCE_DEPOSIT_REBATE`. |
| BALANCE_WITHDRAW_REBATE | 10 | Enum value `BALANCE_WITHDRAW_REBATE`. |
| BALANCE_DEPOSIT_STRATEGY_COMMISSION_OUTER | 11 | Enum value `BALANCE_DEPOSIT_STRATEGY_COMMISSION_OUTER`. |
| BALANCE_WITHDRAW_STRATEGY_COMMISSION_OUTER | 12 | Enum value `BALANCE_WITHDRAW_STRATEGY_COMMISSION_OUTER`. |
| BALANCE_WITHDRAW_BONUS_COMPENSATION | 13 | Enum value `BALANCE_WITHDRAW_BONUS_COMPENSATION`. |
| BALANCE_WITHDRAW_IB_SHARED_PERCENTAGE_TO_BROKER | 14 | Enum value `BALANCE_WITHDRAW_IB_SHARED_PERCENTAGE_TO_BROKER`. |
| BALANCE_DEPOSIT_DIVIDENDS | 15 | Enum value `BALANCE_DEPOSIT_DIVIDENDS`. |
| BALANCE_WITHDRAW_DIVIDENDS | 16 | Enum value `BALANCE_WITHDRAW_DIVIDENDS`. |
| BALANCE_WITHDRAW_GSL_CHARGE | 17 | Enum value `BALANCE_WITHDRAW_GSL_CHARGE`. |
| BALANCE_WITHDRAW_ROLLOVER | 18 | Enum value `BALANCE_WITHDRAW_ROLLOVER`. |
| BALANCE_DEPOSIT_NONWITHDRAWABLE_BONUS | 19 | Enum value `BALANCE_DEPOSIT_NONWITHDRAWABLE_BONUS`. |
| BALANCE_WITHDRAW_NONWITHDRAWABLE_BONUS | 20 | Enum value `BALANCE_WITHDRAW_NONWITHDRAWABLE_BONUS`. |
| BALANCE_DEPOSIT_SWAP | 21 | Enum value `BALANCE_DEPOSIT_SWAP`. |
| BALANCE_WITHDRAW_SWAP | 22 | Enum value `BALANCE_WITHDRAW_SWAP`. |
| BALANCE_DEPOSIT_MANAGEMENT_FEE | 27 | Enum value `BALANCE_DEPOSIT_MANAGEMENT_FEE`. |
| BALANCE_WITHDRAW_MANAGEMENT_FEE | 28 | Enum value `BALANCE_WITHDRAW_MANAGEMENT_FEE`. |
| BALANCE_DEPOSIT_PERFORMANCE_FEE | 29 | Enum value `BALANCE_DEPOSIT_PERFORMANCE_FEE`. |
| BALANCE_WITHDRAW_FOR_SUBACCOUNT | 30 | Enum value `BALANCE_WITHDRAW_FOR_SUBACCOUNT`. |
| BALANCE_DEPOSIT_TO_SUBACCOUNT | 31 | Enum value `BALANCE_DEPOSIT_TO_SUBACCOUNT`. |
| BALANCE_WITHDRAW_FROM_SUBACCOUNT | 32 | Enum value `BALANCE_WITHDRAW_FROM_SUBACCOUNT`. |
| BALANCE_DEPOSIT_FROM_SUBACCOUNT | 33 | Enum value `BALANCE_DEPOSIT_FROM_SUBACCOUNT`. |
| BALANCE_WITHDRAW_COPY_FEE | 34 | Enum value `BALANCE_WITHDRAW_COPY_FEE`. |
| BALANCE_WITHDRAW_INACTIVITY_FEE | 35 | Enum value `BALANCE_WITHDRAW_INACTIVITY_FEE`. |
| BALANCE_DEPOSIT_TRANSFER | 36 | Enum value `BALANCE_DEPOSIT_TRANSFER`. |
| BALANCE_WITHDRAW_TRANSFER | 37 | Enum value `BALANCE_WITHDRAW_TRANSFER`. |
| BALANCE_DEPOSIT_CONVERTED_BONUS | 38 | Enum value `BALANCE_DEPOSIT_CONVERTED_BONUS`. |
| BALANCE_DEPOSIT_NEGATIVE_BALANCE_PROTECTION | 39 | Enum value `BALANCE_DEPOSIT_NEGATIVE_BALANCE_PROTECTION`. |

### ProtoOAChangeBonusType
Inferred description (name-based): Change bonus type
| Name | Value | Inferred description (name-based) |
|---|---|---|
| BONUS_DEPOSIT | 0 | Enum value `BONUS_DEPOSIT`. |
| BONUS_WITHDRAW | 1 | Enum value `BONUS_WITHDRAW`. |

### ProtoOAClientPermissionScope
Inferred description (name-based): Client permission scope
| Name | Value | Inferred description (name-based) |
|---|---|---|
| SCOPE_VIEW | 0 | Enum value `SCOPE_VIEW`. |
| SCOPE_TRADE | 1 | Enum value `SCOPE_TRADE`. |

### ProtoOACommissionType
Inferred description (name-based): Commission type
| Name | Value | Inferred description (name-based) |
|---|---|---|
| USD_PER_MILLION_USD | 1 | Enum value `USD_PER_MILLION_USD`. |
| USD_PER_LOT | 2 | Enum value `USD_PER_LOT`. |
| PERCENTAGE_OF_VALUE | 3 | Enum value `PERCENTAGE_OF_VALUE`. |
| QUOTE_CCY_PER_LOT | 4 | Enum value `QUOTE_CCY_PER_LOT`. |

### ProtoOADayOfWeek
Inferred description (name-based): Day of week
| Name | Value | Inferred description (name-based) |
|---|---|---|
| NONE | 0 | Enum value `NONE`. |
| MONDAY | 1 | Enum value `MONDAY`. |
| TUESDAY | 2 | Enum value `TUESDAY`. |
| WEDNESDAY | 3 | Enum value `WEDNESDAY`. |
| THURSDAY | 4 | Enum value `THURSDAY`. |
| FRIDAY | 5 | Enum value `FRIDAY`. |
| SATURDAY | 6 | Enum value `SATURDAY`. |
| SUNDAY | 7 | Enum value `SUNDAY`. |

### ProtoOADealStatus
Inferred description (name-based): Deal status
| Name | Value | Inferred description (name-based) |
|---|---|---|
| FILLED | 2 | Enum value `FILLED`. |
| PARTIALLY_FILLED | 3 | Enum value `PARTIALLY_FILLED`. |
| REJECTED | 4 | Enum value `REJECTED`. |
| INTERNALLY_REJECTED | 5 | Enum value `INTERNALLY_REJECTED`. |
| ERROR | 6 | Enum value `ERROR`. |
| MISSED | 7 | Enum value `MISSED`. |

### ProtoOAErrorCode
Inferred description (name-based): Error code
| Name | Value | Inferred description (name-based) |
|---|---|---|
| OA_AUTH_TOKEN_EXPIRED | 1 | Enum value `OA_AUTH_TOKEN_EXPIRED`. |
| ACCOUNT_NOT_AUTHORIZED | 2 | Enum value `ACCOUNT_NOT_AUTHORIZED`. |
| ALREADY_LOGGED_IN | 14 | Enum value `ALREADY_LOGGED_IN`. |
| CH_CLIENT_AUTH_FAILURE | 101 | Enum value `CH_CLIENT_AUTH_FAILURE`. |
| CH_CLIENT_NOT_AUTHENTICATED | 102 | Enum value `CH_CLIENT_NOT_AUTHENTICATED`. |
| CH_CLIENT_ALREADY_AUTHENTICATED | 103 | Enum value `CH_CLIENT_ALREADY_AUTHENTICATED`. |
| CH_ACCESS_TOKEN_INVALID | 104 | Enum value `CH_ACCESS_TOKEN_INVALID`. |
| CH_SERVER_NOT_REACHABLE | 105 | Enum value `CH_SERVER_NOT_REACHABLE`. |
| CH_CTID_TRADER_ACCOUNT_NOT_FOUND | 106 | Enum value `CH_CTID_TRADER_ACCOUNT_NOT_FOUND`. |
| CH_OA_CLIENT_NOT_FOUND | 107 | Enum value `CH_OA_CLIENT_NOT_FOUND`. |
| REQUEST_FREQUENCY_EXCEEDED | 108 | Enum value `REQUEST_FREQUENCY_EXCEEDED`. |
| SERVER_IS_UNDER_MAINTENANCE | 109 | Enum value `SERVER_IS_UNDER_MAINTENANCE`. |
| CHANNEL_IS_BLOCKED | 110 | Enum value `CHANNEL_IS_BLOCKED`. |
| CONNECTIONS_LIMIT_EXCEEDED | 67 | Enum value `CONNECTIONS_LIMIT_EXCEEDED`. |
| WORSE_GSL_NOT_ALLOWED | 68 | Enum value `WORSE_GSL_NOT_ALLOWED`. |
| SYMBOL_HAS_HOLIDAY | 69 | Enum value `SYMBOL_HAS_HOLIDAY`. |
| NOT_SUBSCRIBED_TO_SPOTS | 112 | Enum value `NOT_SUBSCRIBED_TO_SPOTS`. |
| ALREADY_SUBSCRIBED | 113 | Enum value `ALREADY_SUBSCRIBED`. |
| SYMBOL_NOT_FOUND | 114 | Enum value `SYMBOL_NOT_FOUND`. |
| UNKNOWN_SYMBOL | 115 | Enum value `UNKNOWN_SYMBOL`. |
| INCORRECT_BOUNDARIES | 35 | Enum value `INCORRECT_BOUNDARIES`. |
| NO_QUOTES | 117 | Enum value `NO_QUOTES`. |
| NOT_ENOUGH_MONEY | 118 | Enum value `NOT_ENOUGH_MONEY`. |
| MAX_EXPOSURE_REACHED | 119 | Enum value `MAX_EXPOSURE_REACHED`. |
| POSITION_NOT_FOUND | 120 | Enum value `POSITION_NOT_FOUND`. |
| ORDER_NOT_FOUND | 121 | Enum value `ORDER_NOT_FOUND`. |
| POSITION_NOT_OPEN | 122 | Enum value `POSITION_NOT_OPEN`. |
| POSITION_LOCKED | 123 | Enum value `POSITION_LOCKED`. |
| TOO_MANY_POSITIONS | 124 | Enum value `TOO_MANY_POSITIONS`. |
| TRADING_BAD_VOLUME | 125 | Enum value `TRADING_BAD_VOLUME`. |
| TRADING_BAD_STOPS | 126 | Enum value `TRADING_BAD_STOPS`. |
| TRADING_BAD_PRICES | 127 | Enum value `TRADING_BAD_PRICES`. |
| TRADING_BAD_STAKE | 128 | Enum value `TRADING_BAD_STAKE`. |
| PROTECTION_IS_TOO_CLOSE_TO_MARKET | 129 | Enum value `PROTECTION_IS_TOO_CLOSE_TO_MARKET`. |
| TRADING_BAD_EXPIRATION_DATE | 130 | Enum value `TRADING_BAD_EXPIRATION_DATE`. |
| PENDING_EXECUTION | 131 | Enum value `PENDING_EXECUTION`. |
| TRADING_DISABLED | 132 | Enum value `TRADING_DISABLED`. |
| TRADING_NOT_ALLOWED | 133 | Enum value `TRADING_NOT_ALLOWED`. |
| UNABLE_TO_CANCEL_ORDER | 134 | Enum value `UNABLE_TO_CANCEL_ORDER`. |
| UNABLE_TO_AMEND_ORDER | 135 | Enum value `UNABLE_TO_AMEND_ORDER`. |
| SHORT_SELLING_NOT_ALLOWED | 136 | Enum value `SHORT_SELLING_NOT_ALLOWED`. |

### ProtoOAExecutionType
Inferred description (name-based): Execution type
| Name | Value | Inferred description (name-based) |
|---|---|---|
| ORDER_ACCEPTED | 2 | Enum value `ORDER_ACCEPTED`. |
| ORDER_FILLED | 3 | Enum value `ORDER_FILLED`. |
| ORDER_REPLACED | 4 | Enum value `ORDER_REPLACED`. |
| ORDER_CANCELLED | 5 | Enum value `ORDER_CANCELLED`. |
| ORDER_EXPIRED | 6 | Enum value `ORDER_EXPIRED`. |
| ORDER_REJECTED | 7 | Enum value `ORDER_REJECTED`. |
| ORDER_CANCEL_REJECTED | 8 | Enum value `ORDER_CANCEL_REJECTED`. |
| SWAP | 9 | Enum value `SWAP`. |
| DEPOSIT_WITHDRAW | 10 | Enum value `DEPOSIT_WITHDRAW`. |
| ORDER_PARTIAL_FILL | 11 | Enum value `ORDER_PARTIAL_FILL`. |
| BONUS_DEPOSIT_WITHDRAW | 12 | Enum value `BONUS_DEPOSIT_WITHDRAW`. |

### ProtoOALimitedRiskMarginCalculationStrategy
Inferred description (name-based): Limited risk margin calculation strategy
| Name | Value | Inferred description (name-based) |
|---|---|---|
| ACCORDING_TO_LEVERAGE | 0 | Enum value `ACCORDING_TO_LEVERAGE`. |
| ACCORDING_TO_GSL | 1 | Enum value `ACCORDING_TO_GSL`. |
| ACCORDING_TO_GSL_AND_LEVERAGE | 2 | Enum value `ACCORDING_TO_GSL_AND_LEVERAGE`. |

### ProtoOAMinCommissionType
Inferred description (name-based): Min commission type
| Name | Value | Inferred description (name-based) |
|---|---|---|
| CURRENCY | 1 | Enum value `CURRENCY`. |
| QUOTE_CURRENCY | 2 | Enum value `QUOTE_CURRENCY`. |

### ProtoOANotificationType
Inferred description (name-based): Notification type
| Name | Value | Inferred description (name-based) |
|---|---|---|
| MARGIN_LEVEL_THRESHOLD_1 | 61 | Enum value `MARGIN_LEVEL_THRESHOLD_1`. |
| MARGIN_LEVEL_THRESHOLD_2 | 62 | Enum value `MARGIN_LEVEL_THRESHOLD_2`. |
| MARGIN_LEVEL_THRESHOLD_3 | 63 | Enum value `MARGIN_LEVEL_THRESHOLD_3`. |

### ProtoOAOrderStatus
Inferred description (name-based): Order status
| Name | Value | Inferred description (name-based) |
|---|---|---|
| ORDER_STATUS_ACCEPTED | 1 | Enum value `ORDER_STATUS_ACCEPTED`. |
| ORDER_STATUS_FILLED | 2 | Enum value `ORDER_STATUS_FILLED`. |
| ORDER_STATUS_REJECTED | 3 | Enum value `ORDER_STATUS_REJECTED`. |
| ORDER_STATUS_EXPIRED | 4 | Enum value `ORDER_STATUS_EXPIRED`. |
| ORDER_STATUS_CANCELLED | 5 | Enum value `ORDER_STATUS_CANCELLED`. |

### ProtoOAOrderTriggerMethod
Inferred description (name-based): Order trigger method
| Name | Value | Inferred description (name-based) |
|---|---|---|
| TRADE | 1 | Enum value `TRADE`. |
| OPPOSITE | 2 | Enum value `OPPOSITE`. |
| DOUBLE_TRADE | 3 | Enum value `DOUBLE_TRADE`. |
| DOUBLE_OPPOSITE | 4 | Enum value `DOUBLE_OPPOSITE`. |

### ProtoOAOrderType
Inferred description (name-based): Order type
| Name | Value | Inferred description (name-based) |
|---|---|---|
| MARKET | 1 | Enum value `MARKET`. |
| LIMIT | 2 | Enum value `LIMIT`. |
| STOP | 3 | Enum value `STOP`. |
| STOP_LOSS_TAKE_PROFIT | 4 | Enum value `STOP_LOSS_TAKE_PROFIT`. |
| MARKET_RANGE | 5 | Enum value `MARKET_RANGE`. |
| STOP_LIMIT | 6 | Enum value `STOP_LIMIT`. |

### ProtoOAPayloadType
Inferred description (name-based): Payload type
| Name | Value | Inferred description (name-based) |
|---|---|---|
| PROTO_OA_APPLICATION_AUTH_REQ | 2100 | Enum value `PROTO_OA_APPLICATION_AUTH_REQ`. |
| PROTO_OA_APPLICATION_AUTH_RES | 2101 | Enum value `PROTO_OA_APPLICATION_AUTH_RES`. |
| PROTO_OA_ACCOUNT_AUTH_REQ | 2102 | Enum value `PROTO_OA_ACCOUNT_AUTH_REQ`. |
| PROTO_OA_ACCOUNT_AUTH_RES | 2103 | Enum value `PROTO_OA_ACCOUNT_AUTH_RES`. |
| PROTO_OA_VERSION_REQ | 2104 | Enum value `PROTO_OA_VERSION_REQ`. |
| PROTO_OA_VERSION_RES | 2105 | Enum value `PROTO_OA_VERSION_RES`. |
| PROTO_OA_NEW_ORDER_REQ | 2106 | Enum value `PROTO_OA_NEW_ORDER_REQ`. |
| PROTO_OA_TRAILING_SL_CHANGED_EVENT | 2107 | Enum value `PROTO_OA_TRAILING_SL_CHANGED_EVENT`. |
| PROTO_OA_CANCEL_ORDER_REQ | 2108 | Enum value `PROTO_OA_CANCEL_ORDER_REQ`. |
| PROTO_OA_AMEND_ORDER_REQ | 2109 | Enum value `PROTO_OA_AMEND_ORDER_REQ`. |
| PROTO_OA_AMEND_POSITION_SLTP_REQ | 2110 | Enum value `PROTO_OA_AMEND_POSITION_SLTP_REQ`. |
| PROTO_OA_CLOSE_POSITION_REQ | 2111 | Enum value `PROTO_OA_CLOSE_POSITION_REQ`. |
| PROTO_OA_ASSET_LIST_REQ | 2112 | Enum value `PROTO_OA_ASSET_LIST_REQ`. |
| PROTO_OA_ASSET_LIST_RES | 2113 | Enum value `PROTO_OA_ASSET_LIST_RES`. |
| PROTO_OA_SYMBOLS_LIST_REQ | 2114 | Enum value `PROTO_OA_SYMBOLS_LIST_REQ`. |
| PROTO_OA_SYMBOLS_LIST_RES | 2115 | Enum value `PROTO_OA_SYMBOLS_LIST_RES`. |
| PROTO_OA_SYMBOL_BY_ID_REQ | 2116 | Enum value `PROTO_OA_SYMBOL_BY_ID_REQ`. |
| PROTO_OA_SYMBOL_BY_ID_RES | 2117 | Enum value `PROTO_OA_SYMBOL_BY_ID_RES`. |
| PROTO_OA_SYMBOLS_FOR_CONVERSION_REQ | 2118 | Enum value `PROTO_OA_SYMBOLS_FOR_CONVERSION_REQ`. |
| PROTO_OA_SYMBOLS_FOR_CONVERSION_RES | 2119 | Enum value `PROTO_OA_SYMBOLS_FOR_CONVERSION_RES`. |
| PROTO_OA_SYMBOL_CHANGED_EVENT | 2120 | Enum value `PROTO_OA_SYMBOL_CHANGED_EVENT`. |
| PROTO_OA_TRADER_REQ | 2121 | Enum value `PROTO_OA_TRADER_REQ`. |
| PROTO_OA_TRADER_RES | 2122 | Enum value `PROTO_OA_TRADER_RES`. |
| PROTO_OA_TRADER_UPDATE_EVENT | 2123 | Enum value `PROTO_OA_TRADER_UPDATE_EVENT`. |
| PROTO_OA_RECONCILE_REQ | 2124 | Enum value `PROTO_OA_RECONCILE_REQ`. |
| PROTO_OA_RECONCILE_RES | 2125 | Enum value `PROTO_OA_RECONCILE_RES`. |
| PROTO_OA_EXECUTION_EVENT | 2126 | Enum value `PROTO_OA_EXECUTION_EVENT`. |
| PROTO_OA_SUBSCRIBE_SPOTS_REQ | 2127 | Enum value `PROTO_OA_SUBSCRIBE_SPOTS_REQ`. |
| PROTO_OA_SUBSCRIBE_SPOTS_RES | 2128 | Enum value `PROTO_OA_SUBSCRIBE_SPOTS_RES`. |
| PROTO_OA_UNSUBSCRIBE_SPOTS_REQ | 2129 | Enum value `PROTO_OA_UNSUBSCRIBE_SPOTS_REQ`. |
| PROTO_OA_UNSUBSCRIBE_SPOTS_RES | 2130 | Enum value `PROTO_OA_UNSUBSCRIBE_SPOTS_RES`. |
| PROTO_OA_SPOT_EVENT | 2131 | Enum value `PROTO_OA_SPOT_EVENT`. |
| PROTO_OA_ORDER_ERROR_EVENT | 2132 | Enum value `PROTO_OA_ORDER_ERROR_EVENT`. |
| PROTO_OA_DEAL_LIST_REQ | 2133 | Enum value `PROTO_OA_DEAL_LIST_REQ`. |
| PROTO_OA_DEAL_LIST_RES | 2134 | Enum value `PROTO_OA_DEAL_LIST_RES`. |
| PROTO_OA_SUBSCRIBE_LIVE_TRENDBAR_REQ | 2135 | Enum value `PROTO_OA_SUBSCRIBE_LIVE_TRENDBAR_REQ`. |
| PROTO_OA_UNSUBSCRIBE_LIVE_TRENDBAR_REQ | 2136 | Enum value `PROTO_OA_UNSUBSCRIBE_LIVE_TRENDBAR_REQ`. |
| PROTO_OA_GET_TRENDBARS_REQ | 2137 | Enum value `PROTO_OA_GET_TRENDBARS_REQ`. |
| PROTO_OA_GET_TRENDBARS_RES | 2138 | Enum value `PROTO_OA_GET_TRENDBARS_RES`. |
| PROTO_OA_EXPECTED_MARGIN_REQ | 2139 | Enum value `PROTO_OA_EXPECTED_MARGIN_REQ`. |
| PROTO_OA_EXPECTED_MARGIN_RES | 2140 | Enum value `PROTO_OA_EXPECTED_MARGIN_RES`. |
| PROTO_OA_MARGIN_CHANGED_EVENT | 2141 | Enum value `PROTO_OA_MARGIN_CHANGED_EVENT`. |
| PROTO_OA_ERROR_RES | 2142 | Enum value `PROTO_OA_ERROR_RES`. |
| PROTO_OA_CASH_FLOW_HISTORY_LIST_REQ | 2143 | Enum value `PROTO_OA_CASH_FLOW_HISTORY_LIST_REQ`. |
| PROTO_OA_CASH_FLOW_HISTORY_LIST_RES | 2144 | Enum value `PROTO_OA_CASH_FLOW_HISTORY_LIST_RES`. |
| PROTO_OA_GET_TICKDATA_REQ | 2145 | Enum value `PROTO_OA_GET_TICKDATA_REQ`. |
| PROTO_OA_GET_TICKDATA_RES | 2146 | Enum value `PROTO_OA_GET_TICKDATA_RES`. |
| PROTO_OA_ACCOUNTS_TOKEN_INVALIDATED_EVENT | 2147 | Enum value `PROTO_OA_ACCOUNTS_TOKEN_INVALIDATED_EVENT`. |
| PROTO_OA_CLIENT_DISCONNECT_EVENT | 2148 | Enum value `PROTO_OA_CLIENT_DISCONNECT_EVENT`. |
| PROTO_OA_GET_ACCOUNTS_BY_ACCESS_TOKEN_REQ | 2149 | Enum value `PROTO_OA_GET_ACCOUNTS_BY_ACCESS_TOKEN_REQ`. |
| PROTO_OA_GET_ACCOUNTS_BY_ACCESS_TOKEN_RES | 2150 | Enum value `PROTO_OA_GET_ACCOUNTS_BY_ACCESS_TOKEN_RES`. |
| PROTO_OA_GET_CTID_PROFILE_BY_TOKEN_REQ | 2151 | Enum value `PROTO_OA_GET_CTID_PROFILE_BY_TOKEN_REQ`. |
| PROTO_OA_GET_CTID_PROFILE_BY_TOKEN_RES | 2152 | Enum value `PROTO_OA_GET_CTID_PROFILE_BY_TOKEN_RES`. |
| PROTO_OA_ASSET_CLASS_LIST_REQ | 2153 | Enum value `PROTO_OA_ASSET_CLASS_LIST_REQ`. |
| PROTO_OA_ASSET_CLASS_LIST_RES | 2154 | Enum value `PROTO_OA_ASSET_CLASS_LIST_RES`. |
| PROTO_OA_DEPTH_EVENT | 2155 | Enum value `PROTO_OA_DEPTH_EVENT`. |
| PROTO_OA_SUBSCRIBE_DEPTH_QUOTES_REQ | 2156 | Enum value `PROTO_OA_SUBSCRIBE_DEPTH_QUOTES_REQ`. |
| PROTO_OA_SUBSCRIBE_DEPTH_QUOTES_RES | 2157 | Enum value `PROTO_OA_SUBSCRIBE_DEPTH_QUOTES_RES`. |
| PROTO_OA_UNSUBSCRIBE_DEPTH_QUOTES_REQ | 2158 | Enum value `PROTO_OA_UNSUBSCRIBE_DEPTH_QUOTES_REQ`. |
| PROTO_OA_UNSUBSCRIBE_DEPTH_QUOTES_RES | 2159 | Enum value `PROTO_OA_UNSUBSCRIBE_DEPTH_QUOTES_RES`. |
| PROTO_OA_SYMBOL_CATEGORY_REQ | 2160 | Enum value `PROTO_OA_SYMBOL_CATEGORY_REQ`. |
| PROTO_OA_SYMBOL_CATEGORY_RES | 2161 | Enum value `PROTO_OA_SYMBOL_CATEGORY_RES`. |
| PROTO_OA_ACCOUNT_LOGOUT_REQ | 2162 | Enum value `PROTO_OA_ACCOUNT_LOGOUT_REQ`. |
| PROTO_OA_ACCOUNT_LOGOUT_RES | 2163 | Enum value `PROTO_OA_ACCOUNT_LOGOUT_RES`. |
| PROTO_OA_ACCOUNT_DISCONNECT_EVENT | 2164 | Enum value `PROTO_OA_ACCOUNT_DISCONNECT_EVENT`. |
| PROTO_OA_SUBSCRIBE_LIVE_TRENDBAR_RES | 2165 | Enum value `PROTO_OA_SUBSCRIBE_LIVE_TRENDBAR_RES`. |
| PROTO_OA_UNSUBSCRIBE_LIVE_TRENDBAR_RES | 2166 | Enum value `PROTO_OA_UNSUBSCRIBE_LIVE_TRENDBAR_RES`. |
| PROTO_OA_MARGIN_CALL_LIST_REQ | 2167 | Enum value `PROTO_OA_MARGIN_CALL_LIST_REQ`. |
| PROTO_OA_MARGIN_CALL_LIST_RES | 2168 | Enum value `PROTO_OA_MARGIN_CALL_LIST_RES`. |
| PROTO_OA_MARGIN_CALL_UPDATE_REQ | 2169 | Enum value `PROTO_OA_MARGIN_CALL_UPDATE_REQ`. |
| PROTO_OA_MARGIN_CALL_UPDATE_RES | 2170 | Enum value `PROTO_OA_MARGIN_CALL_UPDATE_RES`. |
| PROTO_OA_MARGIN_CALL_UPDATE_EVENT | 2171 | Enum value `PROTO_OA_MARGIN_CALL_UPDATE_EVENT`. |
| PROTO_OA_MARGIN_CALL_TRIGGER_EVENT | 2172 | Enum value `PROTO_OA_MARGIN_CALL_TRIGGER_EVENT`. |
| PROTO_OA_REFRESH_TOKEN_REQ | 2173 | Enum value `PROTO_OA_REFRESH_TOKEN_REQ`. |
| PROTO_OA_REFRESH_TOKEN_RES | 2174 | Enum value `PROTO_OA_REFRESH_TOKEN_RES`. |
| PROTO_OA_ORDER_LIST_REQ | 2175 | Enum value `PROTO_OA_ORDER_LIST_REQ`. |
| PROTO_OA_ORDER_LIST_RES | 2176 | Enum value `PROTO_OA_ORDER_LIST_RES`. |
| PROTO_OA_GET_DYNAMIC_LEVERAGE_REQ | 2177 | Enum value `PROTO_OA_GET_DYNAMIC_LEVERAGE_REQ`. |
| PROTO_OA_GET_DYNAMIC_LEVERAGE_RES | 2178 | Enum value `PROTO_OA_GET_DYNAMIC_LEVERAGE_RES`. |
| PROTO_OA_DEAL_LIST_BY_POSITION_ID_REQ | 2179 | Enum value `PROTO_OA_DEAL_LIST_BY_POSITION_ID_REQ`. |
| PROTO_OA_DEAL_LIST_BY_POSITION_ID_RES | 2180 | Enum value `PROTO_OA_DEAL_LIST_BY_POSITION_ID_RES`. |
| PROTO_OA_ORDER_DETAILS_REQ | 2181 | Enum value `PROTO_OA_ORDER_DETAILS_REQ`. |
| PROTO_OA_ORDER_DETAILS_RES | 2182 | Enum value `PROTO_OA_ORDER_DETAILS_RES`. |
| PROTO_OA_ORDER_LIST_BY_POSITION_ID_REQ | 2183 | Enum value `PROTO_OA_ORDER_LIST_BY_POSITION_ID_REQ`. |
| PROTO_OA_ORDER_LIST_BY_POSITION_ID_RES | 2184 | Enum value `PROTO_OA_ORDER_LIST_BY_POSITION_ID_RES`. |
| PROTO_OA_DEAL_OFFSET_LIST_REQ | 2185 | Enum value `PROTO_OA_DEAL_OFFSET_LIST_REQ`. |
| PROTO_OA_DEAL_OFFSET_LIST_RES | 2186 | Enum value `PROTO_OA_DEAL_OFFSET_LIST_RES`. |
| PROTO_OA_GET_POSITION_UNREALIZED_PNL_REQ | 2187 | Enum value `PROTO_OA_GET_POSITION_UNREALIZED_PNL_REQ`. |
| PROTO_OA_GET_POSITION_UNREALIZED_PNL_RES | 2188 | Enum value `PROTO_OA_GET_POSITION_UNREALIZED_PNL_RES`. |

### ProtoOAPositionStatus
Inferred description (name-based): Position status
| Name | Value | Inferred description (name-based) |
|---|---|---|
| POSITION_STATUS_OPEN | 1 | Enum value `POSITION_STATUS_OPEN`. |
| POSITION_STATUS_CLOSED | 2 | Enum value `POSITION_STATUS_CLOSED`. |
| POSITION_STATUS_CREATED | 3 | Enum value `POSITION_STATUS_CREATED`. |
| POSITION_STATUS_ERROR | 4 | Enum value `POSITION_STATUS_ERROR`. |

### ProtoOAQuoteType
Inferred description (name-based): Quote type
| Name | Value | Inferred description (name-based) |
|---|---|---|
| BID | 1 | Enum value `BID`. |
| ASK | 2 | Enum value `ASK`. |

### ProtoOASwapCalculationType
Inferred description (name-based): Swap calculation type
| Name | Value | Inferred description (name-based) |
|---|---|---|
| PIPS | 0 | Enum value `PIPS`. |
| PERCENTAGE | 1 | Enum value `PERCENTAGE`. |

### ProtoOASymbolDistanceType
Inferred description (name-based): Symbol distance type
| Name | Value | Inferred description (name-based) |
|---|---|---|
| SYMBOL_DISTANCE_IN_POINTS | 1 | Enum value `SYMBOL_DISTANCE_IN_POINTS`. |
| SYMBOL_DISTANCE_IN_PERCENTAGE | 2 | Enum value `SYMBOL_DISTANCE_IN_PERCENTAGE`. |

### ProtoOATimeInForce
Inferred description (name-based): Time in force
| Name | Value | Inferred description (name-based) |
|---|---|---|
| GOOD_TILL_DATE | 1 | Enum value `GOOD_TILL_DATE`. |
| GOOD_TILL_CANCEL | 2 | Enum value `GOOD_TILL_CANCEL`. |
| IMMEDIATE_OR_CANCEL | 3 | Enum value `IMMEDIATE_OR_CANCEL`. |
| FILL_OR_KILL | 4 | Enum value `FILL_OR_KILL`. |
| MARKET_ON_OPEN | 5 | Enum value `MARKET_ON_OPEN`. |

### ProtoOATotalMarginCalculationType
Inferred description (name-based): Total margin calculation type
| Name | Value | Inferred description (name-based) |
|---|---|---|
| MAX | 0 | Enum value `MAX`. |
| SUM | 1 | Enum value `SUM`. |
| NET | 2 | Enum value `NET`. |

### ProtoOATradeSide
Inferred description (name-based): Trade side
| Name | Value | Inferred description (name-based) |
|---|---|---|
| BUY | 1 | Enum value `BUY`. |
| SELL | 2 | Enum value `SELL`. |

### ProtoOATradingMode
Inferred description (name-based): Trading mode
| Name | Value | Inferred description (name-based) |
|---|---|---|
| ENABLED | 0 | Enum value `ENABLED`. |
| DISABLED_WITHOUT_PENDINGS_EXECUTION | 1 | Enum value `DISABLED_WITHOUT_PENDINGS_EXECUTION`. |
| DISABLED_WITH_PENDINGS_EXECUTION | 2 | Enum value `DISABLED_WITH_PENDINGS_EXECUTION`. |
| CLOSE_ONLY_MODE | 3 | Enum value `CLOSE_ONLY_MODE`. |

### ProtoOATrendbarPeriod
Inferred description (name-based): Trendbar period
| Name | Value | Inferred description (name-based) |
|---|---|---|
| M1 | 1 | Enum value `M1`. |
| M2 | 2 | Enum value `M2`. |
| M3 | 3 | Enum value `M3`. |
| M4 | 4 | Enum value `M4`. |
| M5 | 5 | Enum value `M5`. |
| M10 | 6 | Enum value `M10`. |
| M15 | 7 | Enum value `M15`. |
| M30 | 8 | Enum value `M30`. |
| H1 | 9 | Enum value `H1`. |
| H4 | 10 | Enum value `H4`. |
| H12 | 11 | Enum value `H12`. |
| D1 | 12 | Enum value `D1`. |
| W1 | 13 | Enum value `W1`. |
| MN1 | 14 | Enum value `MN1`. |

## Common Messages

### ProtoErrorRes
Inferred description (name-based): Error response
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| payloadType | ProtoPayloadType | optional | payload type identifier |
| errorCode | string | optional | error code |
| description | string | optional | text description |
| maintenanceEndTimestamp | uint64 | optional | end timestamp |

### ProtoHeartbeatEvent
Inferred description (name-based): Heartbeat event
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| payloadType | ProtoPayloadType | optional | payload type identifier |

### ProtoMessage
Inferred description (name-based): Message
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| payloadType | uint32 | optional | payload type identifier |
| payload | bytes | optional | payload |
| clientMsgId | string | optional | client message identifier |

## Common Model Messages

### ProtoErrorCode
Inferred description (name-based): Error code
| Name | Value | Inferred description (name-based) |
|---|---|---|
| UNKNOWN_ERROR | 1 | Enum value `UNKNOWN_ERROR`. |
| UNSUPPORTED_MESSAGE | 2 | Enum value `UNSUPPORTED_MESSAGE`. |
| INVALID_REQUEST | 3 | Enum value `INVALID_REQUEST`. |
| TIMEOUT_ERROR | 5 | Enum value `TIMEOUT_ERROR`. |
| ENTITY_NOT_FOUND | 6 | Enum value `ENTITY_NOT_FOUND`. |
| CANT_ROUTE_REQUEST | 7 | Enum value `CANT_ROUTE_REQUEST`. |
| FRAME_TOO_LONG | 8 | Enum value `FRAME_TOO_LONG`. |
| MARKET_CLOSED | 9 | Enum value `MARKET_CLOSED`. |
| CONCURRENT_MODIFICATION | 10 | Enum value `CONCURRENT_MODIFICATION`. |
| BLOCKED_PAYLOAD_TYPE | 11 | Enum value `BLOCKED_PAYLOAD_TYPE`. |

### ProtoPayloadType
Inferred description (name-based): Payload type
| Name | Value | Inferred description (name-based) |
|---|---|---|
| PROTO_MESSAGE | 5 | Enum value `PROTO_MESSAGE`. |
| ERROR_RES | 50 | Enum value `ERROR_RES`. |
| HEARTBEAT_EVENT | 51 | Enum value `HEARTBEAT_EVENT`. |
