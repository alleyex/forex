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
| payloadType | ProtoOAPayloadType | optional | payload type |
| ctidTraderAccountId | int64 | optional | trading account ID |
| accessToken | string | optional | access token |

### ProtoOAAccountAuthRes
Inferred description (name-based): Account authentication response
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | payload type |
| ctidTraderAccountId | int64 | optional | trading account ID |

### ProtoOAAccountDisconnectEvent
Inferred description (name-based): Account disconnect event
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | payload type |
| ctidTraderAccountId | int64 | optional | trading account ID |

### ProtoOAAccountLogoutReq
Inferred description (name-based): Account logout request
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | payload type |
| ctidTraderAccountId | int64 | optional | trading account ID |

### ProtoOAAccountLogoutRes
Inferred description (name-based): Account logout response
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | payload type |
| ctidTraderAccountId | int64 | optional | trading account ID |

### ProtoOAAccountsTokenInvalidatedEvent
Inferred description (name-based): Accounts token invalidated event
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | payload type |
| ctidTraderAccountIds | int64 | repeated | trading account IDs |
| reason | string | optional | reason |

### ProtoOAAmendOrderReq
Inferred description (name-based): Amend order request
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | payload type |
| ctidTraderAccountId | int64 | optional | trading account ID |
| orderId | int64 | optional | order ID |
| volume | int64 | optional | volume |
| limitPrice | double | optional | price |
| stopPrice | double | optional | price |
| expirationTimestamp | int64 | optional | timestamp |
| stopLoss | double | optional | loss |
| takeProfit | double | optional | profit |
| slippageInPoints | int32 | optional | InPoints |
| relativeStopLoss | int64 | optional | stop loss |
| relativeTakeProfit | int64 | optional | take profit |
| guaranteedStopLoss | bool | optional | stop loss |
| trailingStopLoss | bool | optional | stop loss |
| stopTriggerMethod | ProtoOAOrderTriggerMethod | optional | TriggerMethod |

### ProtoOAAmendPositionSLTPReq
Inferred description (name-based): Amend position SL/TP request
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | payload type |
| ctidTraderAccountId | int64 | optional | trading account ID |
| positionId | int64 | optional | position ID |
| stopLoss | double | optional | loss |
| takeProfit | double | optional | profit |
| guaranteedStopLoss | bool | optional | stop loss |
| trailingStopLoss | bool | optional | stop loss |
| stopLossTriggerMethod | ProtoOAOrderTriggerMethod | optional | lossTriggerMethod |

### ProtoOAApplicationAuthReq
Inferred description (name-based): Application authentication request
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | payload type |
| clientId | string | optional | ID |
| clientSecret | string | optional | Secret |

### ProtoOAApplicationAuthRes
Inferred description (name-based): Application authentication response
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | payload type |

### ProtoOAAssetClassListReq
Inferred description (name-based): Asset class list request
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | payload type |
| ctidTraderAccountId | int64 | optional | trading account ID |

### ProtoOAAssetClassListRes
Inferred description (name-based): Asset class list response
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | payload type |
| ctidTraderAccountId | int64 | optional | trading account ID |
| assetClass | ProtoOAAssetClass | repeated | Class |

### ProtoOAAssetListReq
Inferred description (name-based): Asset list request
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | payload type |
| ctidTraderAccountId | int64 | optional | trading account ID |

### ProtoOAAssetListRes
Inferred description (name-based): Asset list response
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | payload type |
| ctidTraderAccountId | int64 | optional | trading account ID |
| asset | ProtoOAAsset | repeated | asset |

### ProtoOACancelOrderReq
Inferred description (name-based): Cancel order request
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | payload type |
| ctidTraderAccountId | int64 | optional | trading account ID |
| orderId | int64 | optional | order ID |

### ProtoOACashFlowHistoryListReq
Inferred description (name-based): Cash flow history list request
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | payload type |
| ctidTraderAccountId | int64 | optional | trading account ID |
| fromTimestamp | int64 | optional | timestamp |
| toTimestamp | int64 | optional | timestamp |

### ProtoOACashFlowHistoryListRes
Inferred description (name-based): Cash flow history list response
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | payload type |
| ctidTraderAccountId | int64 | optional | trading account ID |
| depositWithdraw | ProtoOADepositWithdraw | repeated | Withdraw |

### ProtoOAClientDisconnectEvent
Inferred description (name-based): Client disconnect event
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | payload type |
| reason | string | optional | reason |

### ProtoOAClosePositionReq
Inferred description (name-based): Close position request
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | payload type |
| ctidTraderAccountId | int64 | optional | trading account ID |
| positionId | int64 | optional | position ID |
| volume | int64 | optional | volume |

### ProtoOADealListByPositionIdReq
Inferred description (name-based): Deal list by position ID request
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | payload type |
| ctidTraderAccountId | int64 | optional | trading account ID |
| positionId | int64 | optional | position ID |
| fromTimestamp | int64 | optional | timestamp |
| toTimestamp | int64 | optional | timestamp |

### ProtoOADealListByPositionIdRes
Inferred description (name-based): Deal list by position ID response
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | payload type |
| ctidTraderAccountId | int64 | optional | trading account ID |
| deal | ProtoOADeal | repeated | deal |
| hasMore | int64 | optional | More |

### ProtoOADealListReq
Inferred description (name-based): Deal list request
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | payload type |
| ctidTraderAccountId | int64 | optional | trading account ID |
| fromTimestamp | int64 | optional | timestamp |
| toTimestamp | int64 | optional | timestamp |
| maxRows | int32 | optional | Rows |

### ProtoOADealListRes
Inferred description (name-based): Deal list response
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | payload type |
| ctidTraderAccountId | int64 | optional | trading account ID |
| deal | ProtoOADeal | repeated | deal |
| hasMore | bool | optional | More |

### ProtoOADealOffsetListReq
Inferred description (name-based): Deal offset list request
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | payload type |
| ctidTraderAccountId | int64 | optional | trading account ID |
| dealId | int64 | optional | ID |

### ProtoOADealOffsetListRes
Inferred description (name-based): Deal offset list response
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | payload type |
| ctidTraderAccountId | int64 | optional | trading account ID |
| offsetBy | ProtoOADealOffset | repeated | by |
| offsetting | ProtoOADealOffset | repeated | offsetting |

### ProtoOADepthEvent
Inferred description (name-based): Depth event
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | payload type |
| ctidTraderAccountId | int64 | optional | trading account ID |
| symbolId | uint64 | optional | ID |
| newQuotes | ProtoOADepthQuote | repeated | Quotes |
| deletedQuotes | uint64 | repeated | Quotes |

### ProtoOAErrorRes
Inferred description (name-based): Error response
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | payload type |
| ctidTraderAccountId | int64 | optional | trading account ID |
| errorCode | string | optional | Code |
| description | string | optional | description |
| maintenanceEndTimestamp | int64 | optional | end timestamp |

### ProtoOAExecutionEvent
Inferred description (name-based): Execution event
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | payload type |
| ctidTraderAccountId | int64 | optional | trading account ID |
| executionType | ProtoOAExecutionType | optional | type |
| position | ProtoOAPosition | optional | position |
| order | ProtoOAOrder | optional | order |
| deal | ProtoOADeal | optional | deal |
| bonusDepositWithdraw | ProtoOABonusDepositWithdraw | optional | DepositWithdraw |
| depositWithdraw | ProtoOADepositWithdraw | optional | Withdraw |
| errorCode | string | optional | Code |
| isServerEvent | bool | optional | Serverevent |

### ProtoOAExpectedMarginReq
Inferred description (name-based): Expected margin request
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | payload type |
| ctidTraderAccountId | int64 | optional | trading account ID |
| symbolId | int64 | optional | ID |
| volume | int64 | repeated | volume |

### ProtoOAExpectedMarginRes
Inferred description (name-based): Expected margin response
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | payload type |
| ctidTraderAccountId | int64 | optional | trading account ID |
| margin | ProtoOAExpectedMargin | repeated | margin |
| moneyDigits | uint32 | optional | Digits |

### ProtoOAGetAccountListByAccessTokenReq
Inferred description (name-based): Get account list by access token request
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | payload type |
| accessToken | string | optional | access token |

### ProtoOAGetAccountListByAccessTokenRes
Inferred description (name-based): Get account list by access token response
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | payload type |
| accessToken | string | optional | access token |
| permissionScope | ProtoOAClientPermissionScope | optional | Scope |
| ctidTraderAccount | ProtoOACtidTraderAccount | repeated | trading account |

### ProtoOAGetCtidProfileByTokenReq
Inferred description (name-based): Get CTID profile by token request
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | payload type |
| accessToken | string | optional | access token |

### ProtoOAGetCtidProfileByTokenRes
Inferred description (name-based): Get CTID profile by token response
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | payload type |
| profile | ProtoOACtidProfile | optional | profile |

### ProtoOAGetDynamicLeverageByIDReq
Inferred description (name-based): Get dynamic leverage by ID request
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | payload type |
| ctidTraderAccountId | int64 | optional | trading account ID |
| leverageId | int64 | optional | ID |

### ProtoOAGetDynamicLeverageByIDRes
Inferred description (name-based): Get dynamic leverage by ID response
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | payload type |
| ctidTraderAccountId | int64 | optional | trading account ID |
| leverage | ProtoOADynamicLeverage | optional | leverage |

### ProtoOAGetPositionUnrealizedPnLReq
Inferred description (name-based): Get position unrealized pn l request
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | payload type |
| ctidTraderAccountId | int64 | optional | trading account ID |

### ProtoOAGetPositionUnrealizedPnLRes
Inferred description (name-based): Get position unrealized pn l response
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | payload type |
| ctidTraderAccountId | int64 | optional | trading account ID |
| positionUnrealizedPnL | ProtoOAPositionUnrealizedPnL | repeated | UnrealizedPnL |
| moneyDigits | uint32 | optional | Digits |

### ProtoOAGetTickDataReq
Inferred description (name-based): Get tick data request
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | payload type |
| ctidTraderAccountId | int64 | optional | trading account ID |
| symbolId | int64 | optional | ID |
| type | ProtoOAQuoteType | optional | type |
| fromTimestamp | int64 | optional | timestamp |
| toTimestamp | int64 | optional | timestamp |

### ProtoOAGetTickDataRes
Inferred description (name-based): Get tick data response
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | payload type |
| ctidTraderAccountId | int64 | optional | trading account ID |
| tickData | ProtoOATickData | repeated | Data |
| hasMore | bool | optional | More |

### ProtoOAGetTrendbarsReq
Inferred description (name-based): Get trendbars request
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | payload type |
| ctidTraderAccountId | int64 | optional | trading account ID |
| fromTimestamp | int64 | optional | timestamp |
| toTimestamp | int64 | optional | timestamp |
| period | ProtoOATrendbarPeriod | optional | period |
| symbolId | int64 | optional | ID |
| count | uint32 | optional | count |

### ProtoOAGetTrendbarsRes
Inferred description (name-based): Get trendbars response
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | payload type |
| ctidTraderAccountId | int64 | optional | trading account ID |
| period | ProtoOATrendbarPeriod | optional | period |
| timestamp | int64 | optional | timestamp |
| trendbar | ProtoOATrendbar | repeated | trendbar |
| symbolId | int64 | optional | ID |

### ProtoOAMarginCallListReq
Inferred description (name-based): Margin call list request
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | payload type |
| ctidTraderAccountId | int64 | optional | trading account ID |

### ProtoOAMarginCallListRes
Inferred description (name-based): Margin call list response
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | payload type |
| marginCall | ProtoOAMarginCall | repeated | Call |

### ProtoOAMarginCallTriggerEvent
Inferred description (name-based): Margin call trigger event
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | payload type |
| ctidTraderAccountId | int64 | optional | trading account ID |
| marginCall | ProtoOAMarginCall | optional | Call |

### ProtoOAMarginCallUpdateEvent
Inferred description (name-based): Margin call update event
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | payload type |
| ctidTraderAccountId | int64 | optional | trading account ID |
| marginCall | ProtoOAMarginCall | optional | Call |

### ProtoOAMarginCallUpdateReq
Inferred description (name-based): Margin call update request
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | payload type |
| ctidTraderAccountId | int64 | optional | trading account ID |
| marginCall | ProtoOAMarginCall | optional | Call |

### ProtoOAMarginCallUpdateRes
Inferred description (name-based): Margin call update response
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | payload type |

### ProtoOAMarginChangedEvent
Inferred description (name-based): Margin changed event
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | payload type |
| ctidTraderAccountId | int64 | optional | trading account ID |
| positionId | uint64 | optional | ID |
| usedMargin | uint64 | optional | margin |
| moneyDigits | uint32 | optional | Digits |

### ProtoOANewOrderReq
Inferred description (name-based): New order request
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | payload type |
| ctidTraderAccountId | int64 | optional | trading account ID |
| symbolId | int64 | optional | ID |
| orderType | ProtoOAOrderType | optional | type |
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
| slippageInPoints | int32 | optional | InPoints |
| label | string | optional | label |
| positionId | int64 | optional | position ID |
| clientOrderId | string | optional | orderID |
| relativeStopLoss | int64 | optional | stop loss |
| relativeTakeProfit | int64 | optional | take profit |
| guaranteedStopLoss | bool | optional | stop loss |
| trailingStopLoss | bool | optional | stop loss |
| stopTriggerMethod | ProtoOAOrderTriggerMethod | optional | TriggerMethod |

### ProtoOAOrderDetailsReq
Inferred description (name-based): Order details request
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | payload type |
| ctidTraderAccountId | int64 | optional | trading account ID |
| orderId | int64 | optional | order ID |

### ProtoOAOrderDetailsRes
Inferred description (name-based): Order details response
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | payload type |
| ctidTraderAccountId | int64 | optional | trading account ID |
| order | ProtoOAOrder | optional | order |
| deal | ProtoOADeal | repeated | deal |

### ProtoOAOrderErrorEvent
Inferred description (name-based): Order error event
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | payload type |
| ctidTraderAccountId | int64 | optional | trading account ID |
| errorCode | string | optional | Code |
| orderId | int64 | optional | order ID |
| positionId | int64 | optional | position ID |
| description | string | optional | description |

### ProtoOAOrderListByPositionIdReq
Inferred description (name-based): Order list by position ID request
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | payload type |
| ctidTraderAccountId | int64 | optional | trading account ID |
| positionId | int64 | optional | position ID |
| fromTimestamp | int64 | optional | timestamp |
| toTimestamp | int64 | optional | timestamp |

### ProtoOAOrderListByPositionIdRes
Inferred description (name-based): Order list by position ID response
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | payload type |
| ctidTraderAccountId | int64 | optional | trading account ID |
| order | ProtoOAOrder | repeated | order |
| hasMore | bool | optional | More |

### ProtoOAOrderListReq
Inferred description (name-based): Order list request
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | payload type |
| ctidTraderAccountId | int64 | optional | trading account ID |
| fromTimestamp | int64 | optional | timestamp |
| toTimestamp | int64 | optional | timestamp |

### ProtoOAOrderListRes
Inferred description (name-based): Order list response
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | payload type |
| ctidTraderAccountId | int64 | optional | trading account ID |
| order | ProtoOAOrder | repeated | order |
| hasMore | bool | optional | More |

### ProtoOAReconcileReq
Inferred description (name-based): Reconcile request
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | payload type |
| ctidTraderAccountId | int64 | optional | trading account ID |

### ProtoOAReconcileRes
Inferred description (name-based): Reconcile response
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | payload type |
| ctidTraderAccountId | int64 | optional | trading account ID |
| position | ProtoOAPosition | repeated | position |
| order | ProtoOAOrder | repeated | order |

### ProtoOARefreshTokenReq
Inferred description (name-based): Refresh token request
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | payload type |
| refreshToken | string | optional | Token |

### ProtoOARefreshTokenRes
Inferred description (name-based): Refresh token response
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | payload type |
| accessToken | string | optional | access token |
| tokenType | string | optional | type |
| expiresIn | int64 | optional | In |
| refreshToken | string | optional | Token |

### ProtoOASpotEvent
Inferred description (name-based): Spot event
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | payload type |
| ctidTraderAccountId | int64 | optional | trading account ID |
| symbolId | int64 | optional | ID |
| bid | uint64 | optional | bid |
| ask | uint64 | optional | ask |
| trendbar | ProtoOATrendbar | repeated | trendbar |
| sessionClose | uint64 | optional | close |
| timestamp | int64 | optional | timestamp |

### ProtoOASubscribeDepthQuotesReq
Inferred description (name-based): Subscribe depth quotes request
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | payload type |
| ctidTraderAccountId | int64 | optional | trading account ID |
| symbolId | int64 | repeated | ID |

### ProtoOASubscribeDepthQuotesRes
Inferred description (name-based): Subscribe depth quotes response
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | payload type |
| ctidTraderAccountId | int64 | optional | trading account ID |

### ProtoOASubscribeLiveTrendbarReq
Inferred description (name-based): Subscribe live trendbar request
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | payload type |
| ctidTraderAccountId | int64 | optional | trading account ID |
| period | ProtoOATrendbarPeriod | optional | period |
| symbolId | int64 | optional | ID |

### ProtoOASubscribeLiveTrendbarRes
Inferred description (name-based): Subscribe live trendbar response
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | payload type |
| ctidTraderAccountId | int64 | optional | trading account ID |

### ProtoOASubscribeSpotsReq
Inferred description (name-based): Subscribe spots request
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | payload type |
| ctidTraderAccountId | int64 | optional | trading account ID |
| symbolId | int64 | repeated | ID |
| subscribeToSpotTimestamp | bool | optional | Tospot quotetimestamp |

### ProtoOASubscribeSpotsRes
Inferred description (name-based): Subscribe spots response
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | payload type |
| ctidTraderAccountId | int64 | optional | trading account ID |

### ProtoOASymbolByIdReq
Inferred description (name-based): Symbol by ID request
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | payload type |
| ctidTraderAccountId | int64 | optional | trading account ID |
| symbolId | int64 | repeated | ID |

### ProtoOASymbolByIdRes
Inferred description (name-based): Symbol by ID response
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | payload type |
| ctidTraderAccountId | int64 | optional | trading account ID |
| symbol | ProtoOASymbol | repeated | symbol |
| archivedSymbol | ProtoOAArchivedSymbol | repeated | symbol |

### ProtoOASymbolCategoryListReq
Inferred description (name-based): Symbol category list request
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | payload type |
| ctidTraderAccountId | int64 | optional | trading account ID |

### ProtoOASymbolCategoryListRes
Inferred description (name-based): Symbol category list response
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | payload type |
| ctidTraderAccountId | int64 | optional | trading account ID |
| symbolCategory | ProtoOASymbolCategory | repeated | Category |

### ProtoOASymbolChangedEvent
Inferred description (name-based): Symbol changed event
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | payload type |
| ctidTraderAccountId | int64 | optional | trading account ID |
| symbolId | int64 | repeated | ID |

### ProtoOASymbolsForConversionReq
Inferred description (name-based): Symbols for conversion request
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | payload type |
| ctidTraderAccountId | int64 | optional | trading account ID |
| firstAssetId | int64 | optional | asset ID |
| lastAssetId | int64 | optional | asset ID |

### ProtoOASymbolsForConversionRes
Inferred description (name-based): Symbols for conversion response
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | payload type |
| ctidTraderAccountId | int64 | optional | trading account ID |
| symbol | ProtoOALightSymbol | repeated | symbol |

### ProtoOASymbolsListReq
Inferred description (name-based): Symbols list request
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | payload type |
| ctidTraderAccountId | int64 | optional | trading account ID |
| includeArchivedSymbols | bool | optional | Archivedsymbol |

### ProtoOASymbolsListRes
Inferred description (name-based): Symbols list response
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | payload type |
| ctidTraderAccountId | int64 | optional | trading account ID |
| symbol | ProtoOALightSymbol | repeated | symbol |
| archivedSymbol | ProtoOAArchivedSymbol | repeated | symbol |

### ProtoOATraderReq
Inferred description (name-based): Trader request
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | payload type |
| ctidTraderAccountId | int64 | optional | trading account ID |

### ProtoOATraderRes
Inferred description (name-based): Trader response
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | payload type |
| ctidTraderAccountId | int64 | optional | trading account ID |
| trader | ProtoOATrader | optional | trader |

### ProtoOATraderUpdatedEvent
Inferred description (name-based): Trader updated event
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | payload type |
| ctidTraderAccountId | int64 | optional | trading account ID |
| trader | ProtoOATrader | optional | trader |

### ProtoOATrailingSLChangedEvent
Inferred description (name-based): Trailing sl changed event
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | payload type |
| ctidTraderAccountId | int64 | optional | trading account ID |
| positionId | int64 | optional | position ID |
| orderId | int64 | optional | order ID |
| stopPrice | double | optional | price |
| utcLastUpdateTimestamp | int64 | optional | last update timestamp |

### ProtoOAUnsubscribeDepthQuotesReq
Inferred description (name-based): Unsubscribe depth quotes request
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | payload type |
| ctidTraderAccountId | int64 | optional | trading account ID |
| symbolId | int64 | repeated | ID |

### ProtoOAUnsubscribeDepthQuotesRes
Inferred description (name-based): Unsubscribe depth quotes response
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | payload type |
| ctidTraderAccountId | int64 | optional | trading account ID |

### ProtoOAUnsubscribeLiveTrendbarReq
Inferred description (name-based): Unsubscribe live trendbar request
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | payload type |
| ctidTraderAccountId | int64 | optional | trading account ID |
| period | ProtoOATrendbarPeriod | optional | period |
| symbolId | int64 | optional | ID |

### ProtoOAUnsubscribeLiveTrendbarRes
Inferred description (name-based): Unsubscribe live trendbar response
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | payload type |
| ctidTraderAccountId | int64 | optional | trading account ID |

### ProtoOAUnsubscribeSpotsReq
Inferred description (name-based): Unsubscribe spots request
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | payload type |
| ctidTraderAccountId | int64 | optional | trading account ID |
| symbolId | int64 | repeated | ID |

### ProtoOAUnsubscribeSpotsRes
Inferred description (name-based): Unsubscribe spots response
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | payload type |
| ctidTraderAccountId | int64 | optional | trading account ID |

### ProtoOAVersionReq
Inferred description (name-based): Version request
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | payload type |

### ProtoOAVersionRes
Inferred description (name-based): Version response
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | payload type |
| version | string | optional | version |

## Open API Model Messages

### ProtoOAArchivedSymbol
Inferred description (name-based): Archived symbol
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| symbolId | int64 | optional | ID |
| name | string | optional | name |
| utcLastUpdateTimestamp | int64 | optional | last update timestamp |
| description | string | optional | description |

### ProtoOAAsset
Inferred description (name-based): Asset
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| assetId | int64 | optional | ID |
| name | string | optional | name |
| displayName | string | optional | Name |
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
| operationType | ProtoOAChangeBonusType | optional | type |
| bonusHistoryId | int64 | optional | history ID |
| managerBonus | int64 | optional | Bonus |
| managerDelta | int64 | optional | Delta |
| ibBonus | int64 | optional | Bonus |
| ibDelta | int64 | optional | Delta |
| changeBonusTimestamp | int64 | optional | bonus timestamp |
| externalNote | string | optional | Note |
| introducingBrokerId | int64 | optional | BrokerID |
| moneyDigits | uint32 | optional | Digits |

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
| moneyDigits | uint32 | optional | Digits |
| pnlConversionFee | int64 | optional | conversion fee |

### ProtoOACtidProfile
Inferred description (name-based): CTID profile
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| userId | int64 | optional | ID |

### ProtoOACtidTraderAccount
Inferred description (name-based): CTID trader account
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| ctidTraderAccountId | uint64 | optional | trading account ID |
| isLive | bool | optional | Live |
| traderLogin | int64 | optional | Login |
| lastClosingDealTimestamp | int64 | optional | closing deal timestamp |
| lastBalanceUpdateTimestamp | int64 | optional | balance update timestamp |

### ProtoOADeal
Inferred description (name-based): Deal
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| dealId | int64 | optional | ID |
| orderId | int64 | optional | order ID |
| positionId | int64 | optional | position ID |
| volume | int64 | optional | volume |
| filledVolume | int64 | optional | volume |
| symbolId | int64 | optional | ID |
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
| moneyDigits | uint32 | optional | Digits |

### ProtoOADealOffset
Inferred description (name-based): Deal offset
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| dealId | int64 | optional | ID |
| volume | int64 | optional | volume |
| executionTimestamp | int64 | optional | timestamp |
| executionPrice | double | optional | price |

### ProtoOADepositWithdraw
Inferred description (name-based): Deposit withdraw
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| operationType | ProtoOAChangeBalanceType | optional | type |
| balanceHistoryId | int64 | optional | history ID |
| balance | int64 | optional | balance |
| delta | int64 | optional | delta |
| changeBalanceTimestamp | int64 | optional | balance timestamp |
| externalNote | string | optional | Note |
| balanceVersion | int64 | optional | Version |
| equity | int64 | optional | equity |
| moneyDigits | uint32 | optional | Digits |

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
| leverageId | int64 | optional | ID |
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
| holidayId | int64 | optional | ID |
| name | string | optional | name |
| description | string | optional | description |
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
| symbolId | int64 | optional | ID |
| symbolName | string | optional | Name |
| enabled | bool | optional | enabled |
| baseAssetId | int64 | optional | asset ID |
| quoteAssetId | int64 | optional | asset ID |
| symbolCategoryId | int64 | optional | CategoryID |
| description | string | optional | description |

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
| orderId | int64 | optional | order ID |
| tradeData | ProtoOATradeData | optional | Data |
| orderType | ProtoOAOrderType | optional | type |
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
| positionId | int64 | optional | position ID |
| relativeStopLoss | int64 | optional | stop loss |
| relativeTakeProfit | int64 | optional | take profit |
| isStopOut | bool | optional | stop-out |
| trailingStopLoss | bool | optional | stop loss |
| stopTriggerMethod | ProtoOAOrderTriggerMethod | optional | TriggerMethod |

### ProtoOAPosition
Inferred description (name-based): Position
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| positionId | int64 | optional | position ID |
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
| stopLossTriggerMethod | ProtoOAOrderTriggerMethod | optional | lossTriggerMethod |
| moneyDigits | uint32 | optional | Digits |
| trailingStopLoss | bool | optional | stop loss |

### ProtoOAPositionUnrealizedPnL
Inferred description (name-based): Position unrealized pn l
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| positionId | int64 | optional | position ID |
| grossUnrealizedPnL | int64 | optional | UnrealizedPnL |
| netUnrealizedPnL | int32 | optional | UnrealizedPnL |

### ProtoOASymbol
Inferred description (name-based): Symbol
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| symbolId | int64 | optional | ID |
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
| commissionType | ProtoOACommissionType | optional | type |
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
| leverageId | int64 | optional | ID |
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
| symbolId | int64 | optional | ID |
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
| ctidTraderAccountId | int64 | optional | trading account ID |
| balance | int64 | optional | balance |
| balanceVersion | int64 | optional | Version |
| managerBonus | int64 | optional | Bonus |
| ibBonus | int64 | optional | Bonus |
| nonWithdrawableBonus | int64 | optional | WithdrawableBonus |
| accessRights | ProtoOAAccessRights | optional | Rights |
| depositAssetId | int64 | optional | asset ID |
| swapFree | bool | optional | Free |
| leverageInCents | uint32 | optional | InCents |
| totalMarginCalculationType | ProtoOATotalMarginCalculationType | optional | margin calculation type |
| maxLeverage | uint32 | optional | leverage |
| frenchRisk | bool | optional | risk |
| traderLogin | int64 | optional | Login |
| accountType | ProtoOAAccountType | optional | type |
| brokerName | string | optional | Name |
| registrationTimestamp | int64 | optional | timestamp |
| isLimitedRisk | bool | optional | Limitedrisk |
| limitedRiskMarginCalculationStrategy | ProtoOALimitedRiskMarginCalculationStrategy | optional | risk margin calculation strategy |
| moneyDigits | uint32 | optional | Digits |

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
| FULL_ACCESS | 0 | FULLACCESS |
| CLOSE_ONLY | 1 | CLOSEONLY |
| NO_TRADING | 2 | NOTRADING |
| NO_LOGIN | 3 | NOLOGIN |

### ProtoOAAccountType
Inferred description (name-based): Account type
| Name | Value | Inferred description (name-based) |
|---|---|---|
| HEDGED | 0 | HEDGED |
| NETTED | 1 | NETTED |
| SPREAD_BETTING | 2 | SPREADBETTING |

### ProtoOAChangeBalanceType
Inferred description (name-based): Change balance type
| Name | Value | Inferred description (name-based) |
|---|---|---|
| BALANCE_DEPOSIT | 0 | BALANCEDEPOSIT |
| BALANCE_WITHDRAW | 1 | BALANCEWITHDRAW |
| BALANCE_DEPOSIT_STRATEGY_COMMISSION_INNER | 3 | BALANCEDEPOSITSTRATEGYCOMMISSIONINNER |
| BALANCE_WITHDRAW_STRATEGY_COMMISSION_INNER | 4 | BALANCEWITHDRAWSTRATEGYCOMMISSIONINNER |
| BALANCE_DEPOSIT_IB_COMMISSIONS | 5 | BALANCEDEPOSITIBCOMMISSIONS |
| BALANCE_WITHDRAW_IB_SHARED_PERCENTAGE | 6 | BALANCEWITHDRAWIBSHAREDPERCENTAGE |
| BALANCE_DEPOSIT_IB_SHARED_PERCENTAGE_FROM_SUB_IB | 7 | BALANCEDEPOSITIBSHAREDPERCENTAGEFROMSUBIB |
| BALANCE_DEPOSIT_IB_SHARED_PERCENTAGE_FROM_BROKER | 8 | BALANCEDEPOSITIBSHAREDPERCENTAGEFROMBROKER |
| BALANCE_DEPOSIT_REBATE | 9 | BALANCEDEPOSITREBATE |
| BALANCE_WITHDRAW_REBATE | 10 | BALANCEWITHDRAWREBATE |
| BALANCE_DEPOSIT_STRATEGY_COMMISSION_OUTER | 11 | BALANCEDEPOSITSTRATEGYCOMMISSIONOUTER |
| BALANCE_WITHDRAW_STRATEGY_COMMISSION_OUTER | 12 | BALANCEWITHDRAWSTRATEGYCOMMISSIONOUTER |
| BALANCE_WITHDRAW_BONUS_COMPENSATION | 13 | BALANCEWITHDRAWBONUSCOMPENSATION |
| BALANCE_WITHDRAW_IB_SHARED_PERCENTAGE_TO_BROKER | 14 | BALANCEWITHDRAWIBSHAREDPERCENTAGETOBROKER |
| BALANCE_DEPOSIT_DIVIDENDS | 15 | BALANCEDEPOSITDIVIDENDS |
| BALANCE_WITHDRAW_DIVIDENDS | 16 | BALANCEWITHDRAWDIVIDENDS |
| BALANCE_WITHDRAW_GSL_CHARGE | 17 | BALANCEWITHDRAWGSLCHARGE |
| BALANCE_WITHDRAW_ROLLOVER | 18 | BALANCEWITHDRAWROLLOVER |
| BALANCE_DEPOSIT_NONWITHDRAWABLE_BONUS | 19 | BALANCEDEPOSITNONWITHDRAWABLEBONUS |
| BALANCE_WITHDRAW_NONWITHDRAWABLE_BONUS | 20 | BALANCEWITHDRAWNONWITHDRAWABLEBONUS |
| BALANCE_DEPOSIT_SWAP | 21 | BALANCEDEPOSITSWAP |
| BALANCE_WITHDRAW_SWAP | 22 | BALANCEWITHDRAWSWAP |
| BALANCE_DEPOSIT_MANAGEMENT_FEE | 27 | BALANCEDEPOSITMANAGEMENTFEE |
| BALANCE_WITHDRAW_MANAGEMENT_FEE | 28 | BALANCEWITHDRAWMANAGEMENTFEE |
| BALANCE_DEPOSIT_PERFORMANCE_FEE | 29 | BALANCEDEPOSITPERFORMANCEFEE |
| BALANCE_WITHDRAW_FOR_SUBACCOUNT | 30 | BALANCEWITHDRAWFORSUBACCOUNT |
| BALANCE_DEPOSIT_TO_SUBACCOUNT | 31 | BALANCEDEPOSITTOSUBACCOUNT |
| BALANCE_WITHDRAW_FROM_SUBACCOUNT | 32 | BALANCEWITHDRAWFROMSUBACCOUNT |
| BALANCE_DEPOSIT_FROM_SUBACCOUNT | 33 | BALANCEDEPOSITFROMSUBACCOUNT |
| BALANCE_WITHDRAW_COPY_FEE | 34 | BALANCEWITHDRAWCOPYFEE |
| BALANCE_WITHDRAW_INACTIVITY_FEE | 35 | BALANCEWITHDRAWINACTIVITYFEE |
| BALANCE_DEPOSIT_TRANSFER | 36 | BALANCEDEPOSITTRANSFER |
| BALANCE_WITHDRAW_TRANSFER | 37 | BALANCEWITHDRAWTRANSFER |
| BALANCE_DEPOSIT_CONVERTED_BONUS | 38 | BALANCEDEPOSITCONVERTEDBONUS |
| BALANCE_DEPOSIT_NEGATIVE_BALANCE_PROTECTION | 39 | BALANCEDEPOSITNEGATIVEBALANCEPROTECTION |

### ProtoOAChangeBonusType
Inferred description (name-based): Change bonus type
| Name | Value | Inferred description (name-based) |
|---|---|---|
| BONUS_DEPOSIT | 0 | BONUSDEPOSIT |
| BONUS_WITHDRAW | 1 | BONUSWITHDRAW |

### ProtoOAClientPermissionScope
Inferred description (name-based): Client permission scope
| Name | Value | Inferred description (name-based) |
|---|---|---|
| SCOPE_VIEW | 0 | SCOPEVIEW |
| SCOPE_TRADE | 1 | SCOPETRADE |

### ProtoOACommissionType
Inferred description (name-based): Commission type
| Name | Value | Inferred description (name-based) |
|---|---|---|
| USD_PER_MILLION_USD | 1 | USDPERMILLIONUSD |
| USD_PER_LOT | 2 | USDPERLOT |
| PERCENTAGE_OF_VALUE | 3 | PERCENTAGEOFVALUE |
| QUOTE_CCY_PER_LOT | 4 | QUOTECCYPERLOT |

### ProtoOADayOfWeek
Inferred description (name-based): Day of week
| Name | Value | Inferred description (name-based) |
|---|---|---|
| NONE | 0 | NONE |
| MONDAY | 1 | MONDAY |
| TUESDAY | 2 | TUESDAY |
| WEDNESDAY | 3 | WEDNESDAY |
| THURSDAY | 4 | THURSDAY |
| FRIDAY | 5 | FRIDAY |
| SATURDAY | 6 | SATURDAY |
| SUNDAY | 7 | SUNDAY |

### ProtoOADealStatus
Inferred description (name-based): Deal status
| Name | Value | Inferred description (name-based) |
|---|---|---|
| FILLED | 2 | FILLED |
| PARTIALLY_FILLED | 3 | PARTIALLYFILLED |
| REJECTED | 4 | REJECTED |
| INTERNALLY_REJECTED | 5 | INTERNALLYREJECTED |
| ERROR | 6 | ERROR |
| MISSED | 7 | MISSED |

### ProtoOAErrorCode
Inferred description (name-based): Error code
| Name | Value | Inferred description (name-based) |
|---|---|---|
| OA_AUTH_TOKEN_EXPIRED | 1 | OAAUTHTOKENEXPIRED |
| ACCOUNT_NOT_AUTHORIZED | 2 | ACCOUNTNOTAUTHORIZED |
| ALREADY_LOGGED_IN | 14 | ALREADYLOGGEDIN |
| CH_CLIENT_AUTH_FAILURE | 101 | CHCLIENTAUTHFAILURE |
| CH_CLIENT_NOT_AUTHENTICATED | 102 | CHCLIENTNOTAUTHENTICATED |
| CH_CLIENT_ALREADY_AUTHENTICATED | 103 | CHCLIENTALREADYAUTHENTICATED |
| CH_ACCESS_TOKEN_INVALID | 104 | CHACCESSTOKENINVALID |
| CH_SERVER_NOT_REACHABLE | 105 | CHSERVERNOTREACHABLE |
| CH_CTID_TRADER_ACCOUNT_NOT_FOUND | 106 | CHCTIDTRADERACCOUNTNOTFOUND |
| CH_OA_CLIENT_NOT_FOUND | 107 | CHOACLIENTNOTFOUND |
| REQUEST_FREQUENCY_EXCEEDED | 108 | REQUESTFREQUENCYEXCEEDED |
| SERVER_IS_UNDER_MAINTENANCE | 109 | SERVERISUNDERMAINTENANCE |
| CHANNEL_IS_BLOCKED | 110 | CHANNELISBLOCKED |
| CONNECTIONS_LIMIT_EXCEEDED | 67 | CONNECTIONSLIMITEXCEEDED |
| WORSE_GSL_NOT_ALLOWED | 68 | WORSEGSLNOTALLOWED |
| SYMBOL_HAS_HOLIDAY | 69 | SYMBOLHASHOLIDAY |
| NOT_SUBSCRIBED_TO_SPOTS | 112 | NOTSUBSCRIBEDTOSPOTS |
| ALREADY_SUBSCRIBED | 113 | ALREADYSUBSCRIBED |
| SYMBOL_NOT_FOUND | 114 | SYMBOLNOTFOUND |
| UNKNOWN_SYMBOL | 115 | UNKNOWNSYMBOL |
| INCORRECT_BOUNDARIES | 35 | INCORRECTBOUNDARIES |
| NO_QUOTES | 117 | NOQUOTES |
| NOT_ENOUGH_MONEY | 118 | NOTENOUGHMONEY |
| MAX_EXPOSURE_REACHED | 119 | MAXEXPOSUREREACHED |
| POSITION_NOT_FOUND | 120 | POSITIONNOTFOUND |
| ORDER_NOT_FOUND | 121 | ORDERNOTFOUND |
| POSITION_NOT_OPEN | 122 | POSITIONNOTOPEN |
| POSITION_LOCKED | 123 | POSITIONLOCKED |
| TOO_MANY_POSITIONS | 124 | TOOMANYPOSITIONS |
| TRADING_BAD_VOLUME | 125 | TRADINGBADVOLUME |
| TRADING_BAD_STOPS | 126 | TRADINGBADSTOPS |
| TRADING_BAD_PRICES | 127 | TRADINGBADPRICES |
| TRADING_BAD_STAKE | 128 | TRADINGBADSTAKE |
| PROTECTION_IS_TOO_CLOSE_TO_MARKET | 129 | PROTECTIONISTOOCLOSETOMARKET |
| TRADING_BAD_EXPIRATION_DATE | 130 | TRADINGBADEXPIRATIONDATE |
| PENDING_EXECUTION | 131 | PENDINGEXECUTION |
| TRADING_DISABLED | 132 | TRADINGDISABLED |
| TRADING_NOT_ALLOWED | 133 | TRADINGNOTALLOWED |
| UNABLE_TO_CANCEL_ORDER | 134 | UNABLETOCANCELORDER |
| UNABLE_TO_AMEND_ORDER | 135 | UNABLETOAMENDORDER |
| SHORT_SELLING_NOT_ALLOWED | 136 | SHORTSELLINGNOTALLOWED |

### ProtoOAExecutionType
Inferred description (name-based): Execution type
| Name | Value | Inferred description (name-based) |
|---|---|---|
| ORDER_ACCEPTED | 2 | ORDERACCEPTED |
| ORDER_FILLED | 3 | ORDERFILLED |
| ORDER_REPLACED | 4 | ORDERREPLACED |
| ORDER_CANCELLED | 5 | ORDERCANCELLED |
| ORDER_EXPIRED | 6 | ORDEREXPIRED |
| ORDER_REJECTED | 7 | ORDERREJECTED |
| ORDER_CANCEL_REJECTED | 8 | ORDERCANCELREJECTED |
| SWAP | 9 | SWAP |
| DEPOSIT_WITHDRAW | 10 | DEPOSITWITHDRAW |
| ORDER_PARTIAL_FILL | 11 | ORDERPARTIALFILL |
| BONUS_DEPOSIT_WITHDRAW | 12 | BONUSDEPOSITWITHDRAW |

### ProtoOALimitedRiskMarginCalculationStrategy
Inferred description (name-based): Limited risk margin calculation strategy
| Name | Value | Inferred description (name-based) |
|---|---|---|
| ACCORDING_TO_LEVERAGE | 0 | ACCORDINGTOLEVERAGE |
| ACCORDING_TO_GSL | 1 | ACCORDINGTOGSL |
| ACCORDING_TO_GSL_AND_LEVERAGE | 2 | ACCORDINGTOGSLANDLEVERAGE |

### ProtoOAMinCommissionType
Inferred description (name-based): Min commission type
| Name | Value | Inferred description (name-based) |
|---|---|---|
| CURRENCY | 1 | CURRENCY |
| QUOTE_CURRENCY | 2 | QUOTECURRENCY |

### ProtoOANotificationType
Inferred description (name-based): Notification type
| Name | Value | Inferred description (name-based) |
|---|---|---|
| MARGIN_LEVEL_THRESHOLD_1 | 61 | MARGINLEVELTHRESHOLD |
| MARGIN_LEVEL_THRESHOLD_2 | 62 | MARGINLEVELTHRESHOLD |
| MARGIN_LEVEL_THRESHOLD_3 | 63 | MARGINLEVELTHRESHOLD |

### ProtoOAOrderStatus
Inferred description (name-based): Order status
| Name | Value | Inferred description (name-based) |
|---|---|---|
| ORDER_STATUS_ACCEPTED | 1 | ORDERSTATUSACCEPTED |
| ORDER_STATUS_FILLED | 2 | ORDERSTATUSFILLED |
| ORDER_STATUS_REJECTED | 3 | ORDERSTATUSREJECTED |
| ORDER_STATUS_EXPIRED | 4 | ORDERSTATUSEXPIRED |
| ORDER_STATUS_CANCELLED | 5 | ORDERSTATUSCANCELLED |

### ProtoOAOrderTriggerMethod
Inferred description (name-based): Order trigger method
| Name | Value | Inferred description (name-based) |
|---|---|---|
| TRADE | 1 | TRADE |
| OPPOSITE | 2 | OPPOSITE |
| DOUBLE_TRADE | 3 | DOUBLETRADE |
| DOUBLE_OPPOSITE | 4 | DOUBLEOPPOSITE |

### ProtoOAOrderType
Inferred description (name-based): Order type
| Name | Value | Inferred description (name-based) |
|---|---|---|
| MARKET | 1 | MARKET |
| LIMIT | 2 | LIMIT |
| STOP | 3 | STOP |
| STOP_LOSS_TAKE_PROFIT | 4 | STOPLOSSTAKEPROFIT |
| MARKET_RANGE | 5 | MARKETRANGE |
| STOP_LIMIT | 6 | STOPLIMIT |

### ProtoOAPayloadType
Inferred description (name-based): Payload type
| Name | Value | Inferred description (name-based) |
|---|---|---|
| PROTO_OA_APPLICATION_AUTH_REQ | 2100 | PROTOOAAPPLICATIONAUTHREQ |
| PROTO_OA_APPLICATION_AUTH_RES | 2101 | PROTOOAAPPLICATIONAUTHRES |
| PROTO_OA_ACCOUNT_AUTH_REQ | 2102 | PROTOOAACCOUNTAUTHREQ |
| PROTO_OA_ACCOUNT_AUTH_RES | 2103 | PROTOOAACCOUNTAUTHRES |
| PROTO_OA_VERSION_REQ | 2104 | PROTOOAVERSIONREQ |
| PROTO_OA_VERSION_RES | 2105 | PROTOOAVERSIONRES |
| PROTO_OA_NEW_ORDER_REQ | 2106 | PROTOOANEWORDERREQ |
| PROTO_OA_TRAILING_SL_CHANGED_EVENT | 2107 | PROTOOATRAILINGSLCHANGEDEVENT |
| PROTO_OA_CANCEL_ORDER_REQ | 2108 | PROTOOACANCELORDERREQ |
| PROTO_OA_AMEND_ORDER_REQ | 2109 | PROTOOAAMENDORDERREQ |
| PROTO_OA_AMEND_POSITION_SLTP_REQ | 2110 | PROTOOAAMENDPOSITIONSLTPREQ |
| PROTO_OA_CLOSE_POSITION_REQ | 2111 | PROTOOACLOSEPOSITIONREQ |
| PROTO_OA_ASSET_LIST_REQ | 2112 | PROTOOAASSETLISTREQ |
| PROTO_OA_ASSET_LIST_RES | 2113 | PROTOOAASSETLISTRES |
| PROTO_OA_SYMBOLS_LIST_REQ | 2114 | PROTOOASYMBOLSLISTREQ |
| PROTO_OA_SYMBOLS_LIST_RES | 2115 | PROTOOASYMBOLSLISTRES |
| PROTO_OA_SYMBOL_BY_ID_REQ | 2116 | PROTOOASYMBOLBYIDREQ |
| PROTO_OA_SYMBOL_BY_ID_RES | 2117 | PROTOOASYMBOLBYIDRES |
| PROTO_OA_SYMBOLS_FOR_CONVERSION_REQ | 2118 | PROTOOASYMBOLSFORCONVERSIONREQ |
| PROTO_OA_SYMBOLS_FOR_CONVERSION_RES | 2119 | PROTOOASYMBOLSFORCONVERSIONRES |
| PROTO_OA_SYMBOL_CHANGED_EVENT | 2120 | PROTOOASYMBOLCHANGEDEVENT |
| PROTO_OA_TRADER_REQ | 2121 | PROTOOATRADERREQ |
| PROTO_OA_TRADER_RES | 2122 | PROTOOATRADERRES |
| PROTO_OA_TRADER_UPDATE_EVENT | 2123 | PROTOOATRADERUPDATEEVENT |
| PROTO_OA_RECONCILE_REQ | 2124 | PROTOOARECONCILEREQ |
| PROTO_OA_RECONCILE_RES | 2125 | PROTOOARECONCILERES |
| PROTO_OA_EXECUTION_EVENT | 2126 | PROTOOAEXECUTIONEVENT |
| PROTO_OA_SUBSCRIBE_SPOTS_REQ | 2127 | PROTOOASUBSCRIBESPOTSREQ |
| PROTO_OA_SUBSCRIBE_SPOTS_RES | 2128 | PROTOOASUBSCRIBESPOTSRES |
| PROTO_OA_UNSUBSCRIBE_SPOTS_REQ | 2129 | PROTOOAUNSUBSCRIBESPOTSREQ |
| PROTO_OA_UNSUBSCRIBE_SPOTS_RES | 2130 | PROTOOAUNSUBSCRIBESPOTSRES |
| PROTO_OA_SPOT_EVENT | 2131 | PROTOOASPOTEVENT |
| PROTO_OA_ORDER_ERROR_EVENT | 2132 | PROTOOAORDERERROREVENT |
| PROTO_OA_DEAL_LIST_REQ | 2133 | PROTOOADEALLISTREQ |
| PROTO_OA_DEAL_LIST_RES | 2134 | PROTOOADEALLISTRES |
| PROTO_OA_SUBSCRIBE_LIVE_TRENDBAR_REQ | 2135 | PROTOOASUBSCRIBELIVETRENDBARREQ |
| PROTO_OA_UNSUBSCRIBE_LIVE_TRENDBAR_REQ | 2136 | PROTOOAUNSUBSCRIBELIVETRENDBARREQ |
| PROTO_OA_GET_TRENDBARS_REQ | 2137 | PROTOOAGETTRENDBARSREQ |
| PROTO_OA_GET_TRENDBARS_RES | 2138 | PROTOOAGETTRENDBARSRES |
| PROTO_OA_EXPECTED_MARGIN_REQ | 2139 | PROTOOAEXPECTEDMARGINREQ |
| PROTO_OA_EXPECTED_MARGIN_RES | 2140 | PROTOOAEXPECTEDMARGINRES |
| PROTO_OA_MARGIN_CHANGED_EVENT | 2141 | PROTOOAMARGINCHANGEDEVENT |
| PROTO_OA_ERROR_RES | 2142 | PROTOOAERRORRES |
| PROTO_OA_CASH_FLOW_HISTORY_LIST_REQ | 2143 | PROTOOACASHFLOWHISTORYLISTREQ |
| PROTO_OA_CASH_FLOW_HISTORY_LIST_RES | 2144 | PROTOOACASHFLOWHISTORYLISTRES |
| PROTO_OA_GET_TICKDATA_REQ | 2145 | PROTOOAGETTICKDATAREQ |
| PROTO_OA_GET_TICKDATA_RES | 2146 | PROTOOAGETTICKDATARES |
| PROTO_OA_ACCOUNTS_TOKEN_INVALIDATED_EVENT | 2147 | PROTOOAACCOUNTSTOKENINVALIDATEDEVENT |
| PROTO_OA_CLIENT_DISCONNECT_EVENT | 2148 | PROTOOACLIENTDISCONNECTEVENT |
| PROTO_OA_GET_ACCOUNTS_BY_ACCESS_TOKEN_REQ | 2149 | PROTOOAGETACCOUNTSBYACCESSTOKENREQ |
| PROTO_OA_GET_ACCOUNTS_BY_ACCESS_TOKEN_RES | 2150 | PROTOOAGETACCOUNTSBYACCESSTOKENRES |
| PROTO_OA_GET_CTID_PROFILE_BY_TOKEN_REQ | 2151 | PROTOOAGETCTIDPROFILEBYTOKENREQ |
| PROTO_OA_GET_CTID_PROFILE_BY_TOKEN_RES | 2152 | PROTOOAGETCTIDPROFILEBYTOKENRES |
| PROTO_OA_ASSET_CLASS_LIST_REQ | 2153 | PROTOOAASSETCLASSLISTREQ |
| PROTO_OA_ASSET_CLASS_LIST_RES | 2154 | PROTOOAASSETCLASSLISTRES |
| PROTO_OA_DEPTH_EVENT | 2155 | PROTOOADEPTHEVENT |
| PROTO_OA_SUBSCRIBE_DEPTH_QUOTES_REQ | 2156 | PROTOOASUBSCRIBEDEPTHQUOTESREQ |
| PROTO_OA_SUBSCRIBE_DEPTH_QUOTES_RES | 2157 | PROTOOASUBSCRIBEDEPTHQUOTESRES |
| PROTO_OA_UNSUBSCRIBE_DEPTH_QUOTES_REQ | 2158 | PROTOOAUNSUBSCRIBEDEPTHQUOTESREQ |
| PROTO_OA_UNSUBSCRIBE_DEPTH_QUOTES_RES | 2159 | PROTOOAUNSUBSCRIBEDEPTHQUOTESRES |
| PROTO_OA_SYMBOL_CATEGORY_REQ | 2160 | PROTOOASYMBOLCATEGORYREQ |
| PROTO_OA_SYMBOL_CATEGORY_RES | 2161 | PROTOOASYMBOLCATEGORYRES |
| PROTO_OA_ACCOUNT_LOGOUT_REQ | 2162 | PROTOOAACCOUNTLOGOUTREQ |
| PROTO_OA_ACCOUNT_LOGOUT_RES | 2163 | PROTOOAACCOUNTLOGOUTRES |
| PROTO_OA_ACCOUNT_DISCONNECT_EVENT | 2164 | PROTOOAACCOUNTDISCONNECTEVENT |
| PROTO_OA_SUBSCRIBE_LIVE_TRENDBAR_RES | 2165 | PROTOOASUBSCRIBELIVETRENDBARRES |
| PROTO_OA_UNSUBSCRIBE_LIVE_TRENDBAR_RES | 2166 | PROTOOAUNSUBSCRIBELIVETRENDBARRES |
| PROTO_OA_MARGIN_CALL_LIST_REQ | 2167 | PROTOOAMARGINCALLLISTREQ |
| PROTO_OA_MARGIN_CALL_LIST_RES | 2168 | PROTOOAMARGINCALLLISTRES |
| PROTO_OA_MARGIN_CALL_UPDATE_REQ | 2169 | PROTOOAMARGINCALLUPDATEREQ |
| PROTO_OA_MARGIN_CALL_UPDATE_RES | 2170 | PROTOOAMARGINCALLUPDATERES |
| PROTO_OA_MARGIN_CALL_UPDATE_EVENT | 2171 | PROTOOAMARGINCALLUPDATEEVENT |
| PROTO_OA_MARGIN_CALL_TRIGGER_EVENT | 2172 | PROTOOAMARGINCALLTRIGGEREVENT |
| PROTO_OA_REFRESH_TOKEN_REQ | 2173 | PROTOOAREFRESHTOKENREQ |
| PROTO_OA_REFRESH_TOKEN_RES | 2174 | PROTOOAREFRESHTOKENRES |
| PROTO_OA_ORDER_LIST_REQ | 2175 | PROTOOAORDERLISTREQ |
| PROTO_OA_ORDER_LIST_RES | 2176 | PROTOOAORDERLISTRES |
| PROTO_OA_GET_DYNAMIC_LEVERAGE_REQ | 2177 | PROTOOAGETDYNAMICLEVERAGEREQ |
| PROTO_OA_GET_DYNAMIC_LEVERAGE_RES | 2178 | PROTOOAGETDYNAMICLEVERAGERES |
| PROTO_OA_DEAL_LIST_BY_POSITION_ID_REQ | 2179 | PROTOOADEALLISTBYPOSITIONIDREQ |
| PROTO_OA_DEAL_LIST_BY_POSITION_ID_RES | 2180 | PROTOOADEALLISTBYPOSITIONIDRES |
| PROTO_OA_ORDER_DETAILS_REQ | 2181 | PROTOOAORDERDETAILSREQ |
| PROTO_OA_ORDER_DETAILS_RES | 2182 | PROTOOAORDERDETAILSRES |
| PROTO_OA_ORDER_LIST_BY_POSITION_ID_REQ | 2183 | PROTOOAORDERLISTBYPOSITIONIDREQ |
| PROTO_OA_ORDER_LIST_BY_POSITION_ID_RES | 2184 | PROTOOAORDERLISTBYPOSITIONIDRES |
| PROTO_OA_DEAL_OFFSET_LIST_REQ | 2185 | PROTOOADEALOFFSETLISTREQ |
| PROTO_OA_DEAL_OFFSET_LIST_RES | 2186 | PROTOOADEALOFFSETLISTRES |
| PROTO_OA_GET_POSITION_UNREALIZED_PNL_REQ | 2187 | PROTOOAGETPOSITIONUNREALIZEDPNLREQ |
| PROTO_OA_GET_POSITION_UNREALIZED_PNL_RES | 2188 | PROTOOAGETPOSITIONUNREALIZEDPNLRES |

### ProtoOAPositionStatus
Inferred description (name-based): Position status
| Name | Value | Inferred description (name-based) |
|---|---|---|
| POSITION_STATUS_OPEN | 1 | POSITIONSTATUSOPEN |
| POSITION_STATUS_CLOSED | 2 | POSITIONSTATUSCLOSED |
| POSITION_STATUS_CREATED | 3 | POSITIONSTATUSCREATED |
| POSITION_STATUS_ERROR | 4 | POSITIONSTATUSERROR |

### ProtoOAQuoteType
Inferred description (name-based): Quote type
| Name | Value | Inferred description (name-based) |
|---|---|---|
| BID | 1 | BID |
| ASK | 2 | ASK |

### ProtoOASwapCalculationType
Inferred description (name-based): Swap calculation type
| Name | Value | Inferred description (name-based) |
|---|---|---|
| PIPS | 0 | PIPS |
| PERCENTAGE | 1 | PERCENTAGE |

### ProtoOASymbolDistanceType
Inferred description (name-based): Symbol distance type
| Name | Value | Inferred description (name-based) |
|---|---|---|
| SYMBOL_DISTANCE_IN_POINTS | 1 | SYMBOLDISTANCEINPOINTS |
| SYMBOL_DISTANCE_IN_PERCENTAGE | 2 | SYMBOLDISTANCEINPERCENTAGE |

### ProtoOATimeInForce
Inferred description (name-based): Time in force
| Name | Value | Inferred description (name-based) |
|---|---|---|
| GOOD_TILL_DATE | 1 | GOODTILLDATE |
| GOOD_TILL_CANCEL | 2 | GOODTILLCANCEL |
| IMMEDIATE_OR_CANCEL | 3 | IMMEDIATEORCANCEL |
| FILL_OR_KILL | 4 | FILLORKILL |
| MARKET_ON_OPEN | 5 | MARKETONOPEN |

### ProtoOATotalMarginCalculationType
Inferred description (name-based): Total margin calculation type
| Name | Value | Inferred description (name-based) |
|---|---|---|
| MAX | 0 | MAX |
| SUM | 1 | SUM |
| NET | 2 | NET |

### ProtoOATradeSide
Inferred description (name-based): Trade side
| Name | Value | Inferred description (name-based) |
|---|---|---|
| BUY | 1 | BUY |
| SELL | 2 | SELL |

### ProtoOATradingMode
Inferred description (name-based): Trading mode
| Name | Value | Inferred description (name-based) |
|---|---|---|
| ENABLED | 0 | ENABLED |
| DISABLED_WITHOUT_PENDINGS_EXECUTION | 1 | DISABLEDWITHOUTPENDINGSEXECUTION |
| DISABLED_WITH_PENDINGS_EXECUTION | 2 | DISABLEDWITHPENDINGSEXECUTION |
| CLOSE_ONLY_MODE | 3 | CLOSEONLYMODE |

### ProtoOATrendbarPeriod
Inferred description (name-based): Trendbar period
| Name | Value | Inferred description (name-based) |
|---|---|---|
| M1 | 1 | M1 |
| M2 | 2 | M2 |
| M3 | 3 | M3 |
| M4 | 4 | M4 |
| M5 | 5 | M5 |
| M10 | 6 | M10 |
| M15 | 7 | M15 |
| M30 | 8 | M30 |
| H1 | 9 | H1 |
| H4 | 10 | H4 |
| H12 | 11 | H12 |
| D1 | 12 | D1 |
| W1 | 13 | W1 |
| MN1 | 14 | MN1 |

## Common Messages

### ProtoErrorRes
Inferred description (name-based): Error response
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| payloadType | ProtoPayloadType | optional | payload type |
| errorCode | string | optional | Code |
| description | string | optional | description |
| maintenanceEndTimestamp | uint64 | optional | end timestamp |

### ProtoHeartbeatEvent
Inferred description (name-based): Heartbeat event
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| payloadType | ProtoPayloadType | optional | payload type |

### ProtoMessage
Inferred description (name-based): Message
| Field | Type | Label | Inferred description (name-based) |
|---|---|---|---|
| payloadType | uint32 | optional | payload type |
| payload | bytes | optional | payload |
| clientMsgId | string | optional | MsgID |

## Common Model Messages

### ProtoErrorCode
Inferred description (name-based): Error code
| Name | Value | Inferred description (name-based) |
|---|---|---|
| UNKNOWN_ERROR | 1 | UNKNOWNERROR |
| UNSUPPORTED_MESSAGE | 2 | UNSUPPORTEDMESSAGE |
| INVALID_REQUEST | 3 | INVALIDREQUEST |
| TIMEOUT_ERROR | 5 | TIMEOUTERROR |
| ENTITY_NOT_FOUND | 6 | ENTITYNOTFOUND |
| CANT_ROUTE_REQUEST | 7 | CANTROUTEREQUEST |
| FRAME_TOO_LONG | 8 | FRAMETOOLONG |
| MARKET_CLOSED | 9 | MARKETCLOSED |
| CONCURRENT_MODIFICATION | 10 | CONCURRENTMODIFICATION |
| BLOCKED_PAYLOAD_TYPE | 11 | BLOCKEDPAYLOADTYPE |

### ProtoPayloadType
Inferred description (name-based): Payload type
| Name | Value | Inferred description (name-based) |
|---|---|---|
| PROTO_MESSAGE | 5 | PROTOMESSAGE |
| ERROR_RES | 50 | ERRORRES |
| HEARTBEAT_EVENT | 51 | HEARTBEATEVENT |
