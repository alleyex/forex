# cTrader Open API 全量欄位清單

本文件依據官方 Protobuf 定義自動整理。中文功能解說為名稱直譯/推定，僅供理解用途。

## Open API Messages

### Messages

### ProtoOAAccountAuthReq
中文功能解說（依名稱推定）：ProtoOA帳戶認證請求
| Field | Type | Label | 中文解說(依名稱推定) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | 類型 |
| ctidTraderAccountId | int64 | optional | 交易帳戶帳戶ID |
| accessToken | string | optional | Token |

### ProtoOAAccountAuthRes
中文功能解說（依名稱推定）：ProtoOA帳戶認證回應
| Field | Type | Label | 中文解說(依名稱推定) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | 類型 |
| ctidTraderAccountId | int64 | optional | 交易帳戶帳戶ID |

### ProtoOAAccountDisconnectEvent
中文功能解說（依名稱推定）：ProtoOA帳戶斷線事件
| Field | Type | Label | 中文解說(依名稱推定) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | 類型 |
| ctidTraderAccountId | int64 | optional | 交易帳戶帳戶ID |

### ProtoOAAccountLogoutReq
中文功能解說（依名稱推定）：ProtoOA帳戶登出請求
| Field | Type | Label | 中文解說(依名稱推定) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | 類型 |
| ctidTraderAccountId | int64 | optional | 交易帳戶帳戶ID |

### ProtoOAAccountLogoutRes
中文功能解說（依名稱推定）：ProtoOA帳戶登出回應
| Field | Type | Label | 中文解說(依名稱推定) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | 類型 |
| ctidTraderAccountId | int64 | optional | 交易帳戶帳戶ID |

### ProtoOAAccountsTokenInvalidatedEvent
中文功能解說（依名稱推定）：ProtoOAAccountsTokenInvalidated事件
| Field | Type | Label | 中文解說(依名稱推定) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | 類型 |
| ctidTraderAccountIds | int64 | repeated | 交易帳戶帳戶Ids |
| reason | string | optional | reason |

### ProtoOAAmendOrderReq
中文功能解說（依名稱推定）：ProtoOAAmend訂單請求
| Field | Type | Label | 中文解說(依名稱推定) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | 類型 |
| ctidTraderAccountId | int64 | optional | 交易帳戶帳戶ID |
| orderId | int64 | optional | ID |
| volume | int64 | optional | volume |
| limitPrice | double | optional | 價格 |
| stopPrice | double | optional | 價格 |
| expirationTimestamp | int64 | optional | 時間戳 |
| stopLoss | double | optional | 虧損 |
| takeProfit | double | optional | 獲利 |
| slippageInPoints | int32 | optional | InPoints |
| relativeStopLoss | int64 | optional | 停損虧損 |
| relativeTakeProfit | int64 | optional | 停利獲利 |
| guaranteedStopLoss | bool | optional | 停損虧損 |
| trailingStopLoss | bool | optional | 停損虧損 |
| stopTriggerMethod | ProtoOAOrderTriggerMethod | optional | TriggerMethod |

### ProtoOAAmendPositionSLTPReq
中文功能解說（依名稱推定）：ProtoOAAmend持倉SLTP請求
| Field | Type | Label | 中文解說(依名稱推定) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | 類型 |
| ctidTraderAccountId | int64 | optional | 交易帳戶帳戶ID |
| positionId | int64 | optional | ID |
| stopLoss | double | optional | 虧損 |
| takeProfit | double | optional | 獲利 |
| guaranteedStopLoss | bool | optional | 停損虧損 |
| trailingStopLoss | bool | optional | 停損虧損 |
| stopLossTriggerMethod | ProtoOAOrderTriggerMethod | optional | 虧損TriggerMethod |

### ProtoOAApplicationAuthReq
中文功能解說（依名稱推定）：ProtoOA應用程式認證請求
| Field | Type | Label | 中文解說(依名稱推定) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | 類型 |
| clientId | string | optional | ID |
| clientSecret | string | optional | Secret |

### ProtoOAApplicationAuthRes
中文功能解說（依名稱推定）：ProtoOA應用程式認證回應
| Field | Type | Label | 中文解說(依名稱推定) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | 類型 |

### ProtoOAAssetClassListReq
中文功能解說（依名稱推定）：ProtoOA資產Class清單請求
| Field | Type | Label | 中文解說(依名稱推定) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | 類型 |
| ctidTraderAccountId | int64 | optional | 交易帳戶帳戶ID |

### ProtoOAAssetClassListRes
中文功能解說（依名稱推定）：ProtoOA資產Class清單回應
| Field | Type | Label | 中文解說(依名稱推定) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | 類型 |
| ctidTraderAccountId | int64 | optional | 交易帳戶帳戶ID |
| assetClass | ProtoOAAssetClass | repeated | Class |

### ProtoOAAssetListReq
中文功能解說（依名稱推定）：ProtoOA資產清單請求
| Field | Type | Label | 中文解說(依名稱推定) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | 類型 |
| ctidTraderAccountId | int64 | optional | 交易帳戶帳戶ID |

### ProtoOAAssetListRes
中文功能解說（依名稱推定）：ProtoOA資產清單回應
| Field | Type | Label | 中文解說(依名稱推定) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | 類型 |
| ctidTraderAccountId | int64 | optional | 交易帳戶帳戶ID |
| asset | ProtoOAAsset | repeated | asset |

### ProtoOACancelOrderReq
中文功能解說（依名稱推定）：ProtoOACancel訂單請求
| Field | Type | Label | 中文解說(依名稱推定) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | 類型 |
| ctidTraderAccountId | int64 | optional | 交易帳戶帳戶ID |
| orderId | int64 | optional | ID |

### ProtoOACashFlowHistoryListReq
中文功能解說（依名稱推定）：ProtoOACashFlow歷史清單請求
| Field | Type | Label | 中文解說(依名稱推定) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | 類型 |
| ctidTraderAccountId | int64 | optional | 交易帳戶帳戶ID |
| fromTimestamp | int64 | optional | 時間戳 |
| toTimestamp | int64 | optional | 時間戳 |

### ProtoOACashFlowHistoryListRes
中文功能解說（依名稱推定）：ProtoOACashFlow歷史清單回應
| Field | Type | Label | 中文解說(依名稱推定) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | 類型 |
| ctidTraderAccountId | int64 | optional | 交易帳戶帳戶ID |
| depositWithdraw | ProtoOADepositWithdraw | repeated | Withdraw |

### ProtoOAClientDisconnectEvent
中文功能解說（依名稱推定）：ProtoOAClient斷線事件
| Field | Type | Label | 中文解說(依名稱推定) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | 類型 |
| reason | string | optional | reason |

### ProtoOAClosePositionReq
中文功能解說（依名稱推定）：ProtoOA收盤持倉請求
| Field | Type | Label | 中文解說(依名稱推定) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | 類型 |
| ctidTraderAccountId | int64 | optional | 交易帳戶帳戶ID |
| positionId | int64 | optional | ID |
| volume | int64 | optional | volume |

### ProtoOADealListByPositionIdReq
中文功能解說（依名稱推定）：ProtoOA成交清單依持倉ID請求
| Field | Type | Label | 中文解說(依名稱推定) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | 類型 |
| ctidTraderAccountId | int64 | optional | 交易帳戶帳戶ID |
| positionId | int64 | optional | ID |
| fromTimestamp | int64 | optional | 時間戳 |
| toTimestamp | int64 | optional | 時間戳 |

### ProtoOADealListByPositionIdRes
中文功能解說（依名稱推定）：ProtoOA成交清單依持倉ID回應
| Field | Type | Label | 中文解說(依名稱推定) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | 類型 |
| ctidTraderAccountId | int64 | optional | 交易帳戶帳戶ID |
| deal | ProtoOADeal | repeated | deal |
| hasMore | int64 | optional | More |

### ProtoOADealListReq
中文功能解說（依名稱推定）：ProtoOA成交清單請求
| Field | Type | Label | 中文解說(依名稱推定) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | 類型 |
| ctidTraderAccountId | int64 | optional | 交易帳戶帳戶ID |
| fromTimestamp | int64 | optional | 時間戳 |
| toTimestamp | int64 | optional | 時間戳 |
| maxRows | int32 | optional | Rows |

### ProtoOADealListRes
中文功能解說（依名稱推定）：ProtoOA成交清單回應
| Field | Type | Label | 中文解說(依名稱推定) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | 類型 |
| ctidTraderAccountId | int64 | optional | 交易帳戶帳戶ID |
| deal | ProtoOADeal | repeated | deal |
| hasMore | bool | optional | More |

### ProtoOADealOffsetListReq
中文功能解說（依名稱推定）：ProtoOA成交Offset清單請求
| Field | Type | Label | 中文解說(依名稱推定) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | 類型 |
| ctidTraderAccountId | int64 | optional | 交易帳戶帳戶ID |
| dealId | int64 | optional | ID |

### ProtoOADealOffsetListRes
中文功能解說（依名稱推定）：ProtoOA成交Offset清單回應
| Field | Type | Label | 中文解說(依名稱推定) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | 類型 |
| ctidTraderAccountId | int64 | optional | 交易帳戶帳戶ID |
| offsetBy | ProtoOADealOffset | repeated | 依 |
| offsetting | ProtoOADealOffset | repeated | offsetting |

### ProtoOADepthEvent
中文功能解說（依名稱推定）：ProtoOA深度事件
| Field | Type | Label | 中文解說(依名稱推定) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | 類型 |
| ctidTraderAccountId | int64 | optional | 交易帳戶帳戶ID |
| symbolId | uint64 | optional | ID |
| newQuotes | ProtoOADepthQuote | repeated | Quotes |
| deletedQuotes | uint64 | repeated | Quotes |

### ProtoOAErrorRes
中文功能解說（依名稱推定）：ProtoOA錯誤回應
| Field | Type | Label | 中文解說(依名稱推定) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | 類型 |
| ctidTraderAccountId | int64 | optional | 交易帳戶帳戶ID |
| errorCode | string | optional | Code |
| description | string | optional | description |
| maintenanceEndTimestamp | int64 | optional | End時間戳 |

### ProtoOAExecutionEvent
中文功能解說（依名稱推定）：ProtoOAExecution事件
| Field | Type | Label | 中文解說(依名稱推定) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | 類型 |
| ctidTraderAccountId | int64 | optional | 交易帳戶帳戶ID |
| executionType | ProtoOAExecutionType | optional | 類型 |
| position | ProtoOAPosition | optional | position |
| order | ProtoOAOrder | optional | order |
| deal | ProtoOADeal | optional | deal |
| bonusDepositWithdraw | ProtoOABonusDepositWithdraw | optional | DepositWithdraw |
| depositWithdraw | ProtoOADepositWithdraw | optional | Withdraw |
| errorCode | string | optional | Code |
| isServerEvent | bool | optional | Server事件 |

### ProtoOAExpectedMarginReq
中文功能解說（依名稱推定）：ProtoOA預估保證金請求
| Field | Type | Label | 中文解說(依名稱推定) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | 類型 |
| ctidTraderAccountId | int64 | optional | 交易帳戶帳戶ID |
| symbolId | int64 | optional | ID |
| volume | int64 | repeated | volume |

### ProtoOAExpectedMarginRes
中文功能解說（依名稱推定）：ProtoOA預估保證金回應
| Field | Type | Label | 中文解說(依名稱推定) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | 類型 |
| ctidTraderAccountId | int64 | optional | 交易帳戶帳戶ID |
| margin | ProtoOAExpectedMargin | repeated | margin |
| moneyDigits | uint32 | optional | Digits |

### ProtoOAGetAccountListByAccessTokenReq
中文功能解說（依名稱推定）：ProtoOA取得帳戶清單依AccessToken請求
| Field | Type | Label | 中文解說(依名稱推定) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | 類型 |
| accessToken | string | optional | Token |

### ProtoOAGetAccountListByAccessTokenRes
中文功能解說（依名稱推定）：ProtoOA取得帳戶清單依AccessToken回應
| Field | Type | Label | 中文解說(依名稱推定) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | 類型 |
| accessToken | string | optional | Token |
| permissionScope | ProtoOAClientPermissionScope | optional | Scope |
| ctidTraderAccount | ProtoOACtidTraderAccount | repeated | 交易帳戶帳戶 |

### ProtoOAGetCtidProfileByTokenReq
中文功能解說（依名稱推定）：ProtoOA取得CtidProfile依Token請求
| Field | Type | Label | 中文解說(依名稱推定) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | 類型 |
| accessToken | string | optional | Token |

### ProtoOAGetCtidProfileByTokenRes
中文功能解說（依名稱推定）：ProtoOA取得CtidProfile依Token回應
| Field | Type | Label | 中文解說(依名稱推定) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | 類型 |
| profile | ProtoOACtidProfile | optional | profile |

### ProtoOAGetDynamicLeverageByIDReq
中文功能解說（依名稱推定）：ProtoOA取得動態槓桿依ID請求
| Field | Type | Label | 中文解說(依名稱推定) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | 類型 |
| ctidTraderAccountId | int64 | optional | 交易帳戶帳戶ID |
| leverageId | int64 | optional | ID |

### ProtoOAGetDynamicLeverageByIDRes
中文功能解說（依名稱推定）：ProtoOA取得動態槓桿依ID回應
| Field | Type | Label | 中文解說(依名稱推定) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | 類型 |
| ctidTraderAccountId | int64 | optional | 交易帳戶帳戶ID |
| leverage | ProtoOADynamicLeverage | optional | leverage |

### ProtoOAGetPositionUnrealizedPnLReq
中文功能解說（依名稱推定）：ProtoOA取得持倉UnrealizedPnL請求
| Field | Type | Label | 中文解說(依名稱推定) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | 類型 |
| ctidTraderAccountId | int64 | optional | 交易帳戶帳戶ID |

### ProtoOAGetPositionUnrealizedPnLRes
中文功能解說（依名稱推定）：ProtoOA取得持倉UnrealizedPnL回應
| Field | Type | Label | 中文解說(依名稱推定) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | 類型 |
| ctidTraderAccountId | int64 | optional | 交易帳戶帳戶ID |
| positionUnrealizedPnL | ProtoOAPositionUnrealizedPnL | repeated | UnrealizedPnL |
| moneyDigits | uint32 | optional | Digits |

### ProtoOAGetTickDataReq
中文功能解說（依名稱推定）：ProtoOA取得TickData請求
| Field | Type | Label | 中文解說(依名稱推定) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | 類型 |
| ctidTraderAccountId | int64 | optional | 交易帳戶帳戶ID |
| symbolId | int64 | optional | ID |
| type | ProtoOAQuoteType | optional | type |
| fromTimestamp | int64 | optional | 時間戳 |
| toTimestamp | int64 | optional | 時間戳 |

### ProtoOAGetTickDataRes
中文功能解說（依名稱推定）：ProtoOA取得TickData回應
| Field | Type | Label | 中文解說(依名稱推定) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | 類型 |
| ctidTraderAccountId | int64 | optional | 交易帳戶帳戶ID |
| tickData | ProtoOATickData | repeated | Data |
| hasMore | bool | optional | More |

### ProtoOAGetTrendbarsReq
中文功能解說（依名稱推定）：ProtoOA取得Trendbars請求
| Field | Type | Label | 中文解說(依名稱推定) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | 類型 |
| ctidTraderAccountId | int64 | optional | 交易帳戶帳戶ID |
| fromTimestamp | int64 | optional | 時間戳 |
| toTimestamp | int64 | optional | 時間戳 |
| period | ProtoOATrendbarPeriod | optional | period |
| symbolId | int64 | optional | ID |
| count | uint32 | optional | count |

### ProtoOAGetTrendbarsRes
中文功能解說（依名稱推定）：ProtoOA取得Trendbars回應
| Field | Type | Label | 中文解說(依名稱推定) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | 類型 |
| ctidTraderAccountId | int64 | optional | 交易帳戶帳戶ID |
| period | ProtoOATrendbarPeriod | optional | period |
| timestamp | int64 | optional | timestamp |
| trendbar | ProtoOATrendbar | repeated | trendbar |
| symbolId | int64 | optional | ID |

### ProtoOAMarginCallListReq
中文功能解說（依名稱推定）：ProtoOA保證金Call清單請求
| Field | Type | Label | 中文解說(依名稱推定) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | 類型 |
| ctidTraderAccountId | int64 | optional | 交易帳戶帳戶ID |

### ProtoOAMarginCallListRes
中文功能解說（依名稱推定）：ProtoOA保證金Call清單回應
| Field | Type | Label | 中文解說(依名稱推定) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | 類型 |
| marginCall | ProtoOAMarginCall | repeated | Call |

### ProtoOAMarginCallTriggerEvent
中文功能解說（依名稱推定）：ProtoOA保證金CallTrigger事件
| Field | Type | Label | 中文解說(依名稱推定) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | 類型 |
| ctidTraderAccountId | int64 | optional | 交易帳戶帳戶ID |
| marginCall | ProtoOAMarginCall | optional | Call |

### ProtoOAMarginCallUpdateEvent
中文功能解說（依名稱推定）：ProtoOA保證金CallUpdate事件
| Field | Type | Label | 中文解說(依名稱推定) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | 類型 |
| ctidTraderAccountId | int64 | optional | 交易帳戶帳戶ID |
| marginCall | ProtoOAMarginCall | optional | Call |

### ProtoOAMarginCallUpdateReq
中文功能解說（依名稱推定）：ProtoOA保證金CallUpdate請求
| Field | Type | Label | 中文解說(依名稱推定) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | 類型 |
| ctidTraderAccountId | int64 | optional | 交易帳戶帳戶ID |
| marginCall | ProtoOAMarginCall | optional | Call |

### ProtoOAMarginCallUpdateRes
中文功能解說（依名稱推定）：ProtoOA保證金CallUpdate回應
| Field | Type | Label | 中文解說(依名稱推定) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | 類型 |

### ProtoOAMarginChangedEvent
中文功能解說（依名稱推定）：ProtoOA保證金Changed事件
| Field | Type | Label | 中文解說(依名稱推定) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | 類型 |
| ctidTraderAccountId | int64 | optional | 交易帳戶帳戶ID |
| positionId | uint64 | optional | ID |
| usedMargin | uint64 | optional | 保證金 |
| moneyDigits | uint32 | optional | Digits |

### ProtoOANewOrderReq
中文功能解說（依名稱推定）：ProtoOANew訂單請求
| Field | Type | Label | 中文解說(依名稱推定) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | 類型 |
| ctidTraderAccountId | int64 | optional | 交易帳戶帳戶ID |
| symbolId | int64 | optional | ID |
| orderType | ProtoOAOrderType | optional | 類型 |
| tradeSide | ProtoOATradeSide | optional | 方向 |
| volume | int64 | optional | volume |
| limitPrice | double | optional | 價格 |
| stopPrice | double | optional | 價格 |
| timeInForce | ProtoOATimeInForce | optional | InForce |
| expirationTimestamp | int64 | optional | 時間戳 |
| stopLoss | double | optional | 虧損 |
| takeProfit | double | optional | 獲利 |
| comment | string | optional | comment |
| baseSlippagePrice | double | optional | 滑點價格 |
| slippageInPoints | int32 | optional | InPoints |
| label | string | optional | label |
| positionId | int64 | optional | ID |
| clientOrderId | string | optional | 訂單ID |
| relativeStopLoss | int64 | optional | 停損虧損 |
| relativeTakeProfit | int64 | optional | 停利獲利 |
| guaranteedStopLoss | bool | optional | 停損虧損 |
| trailingStopLoss | bool | optional | 停損虧損 |
| stopTriggerMethod | ProtoOAOrderTriggerMethod | optional | TriggerMethod |

### ProtoOAOrderDetailsReq
中文功能解說（依名稱推定）：ProtoOA訂單Details請求
| Field | Type | Label | 中文解說(依名稱推定) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | 類型 |
| ctidTraderAccountId | int64 | optional | 交易帳戶帳戶ID |
| orderId | int64 | optional | ID |

### ProtoOAOrderDetailsRes
中文功能解說（依名稱推定）：ProtoOA訂單Details回應
| Field | Type | Label | 中文解說(依名稱推定) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | 類型 |
| ctidTraderAccountId | int64 | optional | 交易帳戶帳戶ID |
| order | ProtoOAOrder | optional | order |
| deal | ProtoOADeal | repeated | deal |

### ProtoOAOrderErrorEvent
中文功能解說（依名稱推定）：ProtoOA訂單錯誤事件
| Field | Type | Label | 中文解說(依名稱推定) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | 類型 |
| ctidTraderAccountId | int64 | optional | 交易帳戶帳戶ID |
| errorCode | string | optional | Code |
| orderId | int64 | optional | ID |
| positionId | int64 | optional | ID |
| description | string | optional | description |

### ProtoOAOrderListByPositionIdReq
中文功能解說（依名稱推定）：ProtoOA訂單清單依持倉ID請求
| Field | Type | Label | 中文解說(依名稱推定) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | 類型 |
| ctidTraderAccountId | int64 | optional | 交易帳戶帳戶ID |
| positionId | int64 | optional | ID |
| fromTimestamp | int64 | optional | 時間戳 |
| toTimestamp | int64 | optional | 時間戳 |

### ProtoOAOrderListByPositionIdRes
中文功能解說（依名稱推定）：ProtoOA訂單清單依持倉ID回應
| Field | Type | Label | 中文解說(依名稱推定) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | 類型 |
| ctidTraderAccountId | int64 | optional | 交易帳戶帳戶ID |
| order | ProtoOAOrder | repeated | order |
| hasMore | bool | optional | More |

### ProtoOAOrderListReq
中文功能解說（依名稱推定）：ProtoOA訂單清單請求
| Field | Type | Label | 中文解說(依名稱推定) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | 類型 |
| ctidTraderAccountId | int64 | optional | 交易帳戶帳戶ID |
| fromTimestamp | int64 | optional | 時間戳 |
| toTimestamp | int64 | optional | 時間戳 |

### ProtoOAOrderListRes
中文功能解說（依名稱推定）：ProtoOA訂單清單回應
| Field | Type | Label | 中文解說(依名稱推定) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | 類型 |
| ctidTraderAccountId | int64 | optional | 交易帳戶帳戶ID |
| order | ProtoOAOrder | repeated | order |
| hasMore | bool | optional | More |

### ProtoOAReconcileReq
中文功能解說（依名稱推定）：ProtoOAReconcile請求
| Field | Type | Label | 中文解說(依名稱推定) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | 類型 |
| ctidTraderAccountId | int64 | optional | 交易帳戶帳戶ID |

### ProtoOAReconcileRes
中文功能解說（依名稱推定）：ProtoOAReconcile回應
| Field | Type | Label | 中文解說(依名稱推定) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | 類型 |
| ctidTraderAccountId | int64 | optional | 交易帳戶帳戶ID |
| position | ProtoOAPosition | repeated | position |
| order | ProtoOAOrder | repeated | order |

### ProtoOARefreshTokenReq
中文功能解說（依名稱推定）：ProtoOA刷新Token請求
| Field | Type | Label | 中文解說(依名稱推定) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | 類型 |
| refreshToken | string | optional | Token |

### ProtoOARefreshTokenRes
中文功能解說（依名稱推定）：ProtoOA刷新Token回應
| Field | Type | Label | 中文解說(依名稱推定) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | 類型 |
| accessToken | string | optional | Token |
| tokenType | string | optional | 類型 |
| expiresIn | int64 | optional | In |
| refreshToken | string | optional | Token |

### ProtoOASpotEvent
中文功能解說（依名稱推定）：ProtoOA即時報價事件
| Field | Type | Label | 中文解說(依名稱推定) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | 類型 |
| ctidTraderAccountId | int64 | optional | 交易帳戶帳戶ID |
| symbolId | int64 | optional | ID |
| bid | uint64 | optional | bid |
| ask | uint64 | optional | ask |
| trendbar | ProtoOATrendbar | repeated | trendbar |
| sessionClose | uint64 | optional | 收盤 |
| timestamp | int64 | optional | timestamp |

### ProtoOASubscribeDepthQuotesReq
中文功能解說（依名稱推定）：ProtoOA訂閱深度Quotes請求
| Field | Type | Label | 中文解說(依名稱推定) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | 類型 |
| ctidTraderAccountId | int64 | optional | 交易帳戶帳戶ID |
| symbolId | int64 | repeated | ID |

### ProtoOASubscribeDepthQuotesRes
中文功能解說（依名稱推定）：ProtoOA訂閱深度Quotes回應
| Field | Type | Label | 中文解說(依名稱推定) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | 類型 |
| ctidTraderAccountId | int64 | optional | 交易帳戶帳戶ID |

### ProtoOASubscribeLiveTrendbarReq
中文功能解說（依名稱推定）：ProtoOA訂閱LiveK線請求
| Field | Type | Label | 中文解說(依名稱推定) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | 類型 |
| ctidTraderAccountId | int64 | optional | 交易帳戶帳戶ID |
| period | ProtoOATrendbarPeriod | optional | period |
| symbolId | int64 | optional | ID |

### ProtoOASubscribeLiveTrendbarRes
中文功能解說（依名稱推定）：ProtoOA訂閱LiveK線回應
| Field | Type | Label | 中文解說(依名稱推定) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | 類型 |
| ctidTraderAccountId | int64 | optional | 交易帳戶帳戶ID |

### ProtoOASubscribeSpotsReq
中文功能解說（依名稱推定）：ProtoOA訂閱Spots請求
| Field | Type | Label | 中文解說(依名稱推定) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | 類型 |
| ctidTraderAccountId | int64 | optional | 交易帳戶帳戶ID |
| symbolId | int64 | repeated | ID |
| subscribeToSpotTimestamp | bool | optional | To即時報價時間戳 |

### ProtoOASubscribeSpotsRes
中文功能解說（依名稱推定）：ProtoOA訂閱Spots回應
| Field | Type | Label | 中文解說(依名稱推定) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | 類型 |
| ctidTraderAccountId | int64 | optional | 交易帳戶帳戶ID |

### ProtoOASymbolByIdReq
中文功能解說（依名稱推定）：ProtoOA交易品種依ID請求
| Field | Type | Label | 中文解說(依名稱推定) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | 類型 |
| ctidTraderAccountId | int64 | optional | 交易帳戶帳戶ID |
| symbolId | int64 | repeated | ID |

### ProtoOASymbolByIdRes
中文功能解說（依名稱推定）：ProtoOA交易品種依ID回應
| Field | Type | Label | 中文解說(依名稱推定) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | 類型 |
| ctidTraderAccountId | int64 | optional | 交易帳戶帳戶ID |
| symbol | ProtoOASymbol | repeated | symbol |
| archivedSymbol | ProtoOAArchivedSymbol | repeated | 交易品種 |

### ProtoOASymbolCategoryListReq
中文功能解說（依名稱推定）：ProtoOA交易品種Category清單請求
| Field | Type | Label | 中文解說(依名稱推定) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | 類型 |
| ctidTraderAccountId | int64 | optional | 交易帳戶帳戶ID |

### ProtoOASymbolCategoryListRes
中文功能解說（依名稱推定）：ProtoOA交易品種Category清單回應
| Field | Type | Label | 中文解說(依名稱推定) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | 類型 |
| ctidTraderAccountId | int64 | optional | 交易帳戶帳戶ID |
| symbolCategory | ProtoOASymbolCategory | repeated | Category |

### ProtoOASymbolChangedEvent
中文功能解說（依名稱推定）：ProtoOA交易品種Changed事件
| Field | Type | Label | 中文解說(依名稱推定) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | 類型 |
| ctidTraderAccountId | int64 | optional | 交易帳戶帳戶ID |
| symbolId | int64 | repeated | ID |

### ProtoOASymbolsForConversionReq
中文功能解說（依名稱推定）：ProtoOA交易品種ForConversion請求
| Field | Type | Label | 中文解說(依名稱推定) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | 類型 |
| ctidTraderAccountId | int64 | optional | 交易帳戶帳戶ID |
| firstAssetId | int64 | optional | 資產ID |
| lastAssetId | int64 | optional | 資產ID |

### ProtoOASymbolsForConversionRes
中文功能解說（依名稱推定）：ProtoOA交易品種ForConversion回應
| Field | Type | Label | 中文解說(依名稱推定) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | 類型 |
| ctidTraderAccountId | int64 | optional | 交易帳戶帳戶ID |
| symbol | ProtoOALightSymbol | repeated | symbol |

### ProtoOASymbolsListReq
中文功能解說（依名稱推定）：ProtoOA交易品種清單請求
| Field | Type | Label | 中文解說(依名稱推定) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | 類型 |
| ctidTraderAccountId | int64 | optional | 交易帳戶帳戶ID |
| includeArchivedSymbols | bool | optional | Archived交易品種 |

### ProtoOASymbolsListRes
中文功能解說（依名稱推定）：ProtoOA交易品種清單回應
| Field | Type | Label | 中文解說(依名稱推定) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | 類型 |
| ctidTraderAccountId | int64 | optional | 交易帳戶帳戶ID |
| symbol | ProtoOALightSymbol | repeated | symbol |
| archivedSymbol | ProtoOAArchivedSymbol | repeated | 交易品種 |

### ProtoOATraderReq
中文功能解說（依名稱推定）：ProtoOA交易帳戶請求
| Field | Type | Label | 中文解說(依名稱推定) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | 類型 |
| ctidTraderAccountId | int64 | optional | 交易帳戶帳戶ID |

### ProtoOATraderRes
中文功能解說（依名稱推定）：ProtoOA交易帳戶回應
| Field | Type | Label | 中文解說(依名稱推定) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | 類型 |
| ctidTraderAccountId | int64 | optional | 交易帳戶帳戶ID |
| trader | ProtoOATrader | optional | trader |

### ProtoOATraderUpdatedEvent
中文功能解說（依名稱推定）：ProtoOA交易帳戶Updated事件
| Field | Type | Label | 中文解說(依名稱推定) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | 類型 |
| ctidTraderAccountId | int64 | optional | 交易帳戶帳戶ID |
| trader | ProtoOATrader | optional | trader |

### ProtoOATrailingSLChangedEvent
中文功能解說（依名稱推定）：ProtoOATrailingSLChanged事件
| Field | Type | Label | 中文解說(依名稱推定) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | 類型 |
| ctidTraderAccountId | int64 | optional | 交易帳戶帳戶ID |
| positionId | int64 | optional | ID |
| orderId | int64 | optional | ID |
| stopPrice | double | optional | 價格 |
| utcLastUpdateTimestamp | int64 | optional | LastUpdate時間戳 |

### ProtoOAUnsubscribeDepthQuotesReq
中文功能解說（依名稱推定）：ProtoOA取消訂閱深度Quotes請求
| Field | Type | Label | 中文解說(依名稱推定) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | 類型 |
| ctidTraderAccountId | int64 | optional | 交易帳戶帳戶ID |
| symbolId | int64 | repeated | ID |

### ProtoOAUnsubscribeDepthQuotesRes
中文功能解說（依名稱推定）：ProtoOA取消訂閱深度Quotes回應
| Field | Type | Label | 中文解說(依名稱推定) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | 類型 |
| ctidTraderAccountId | int64 | optional | 交易帳戶帳戶ID |

### ProtoOAUnsubscribeLiveTrendbarReq
中文功能解說（依名稱推定）：ProtoOA取消訂閱LiveK線請求
| Field | Type | Label | 中文解說(依名稱推定) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | 類型 |
| ctidTraderAccountId | int64 | optional | 交易帳戶帳戶ID |
| period | ProtoOATrendbarPeriod | optional | period |
| symbolId | int64 | optional | ID |

### ProtoOAUnsubscribeLiveTrendbarRes
中文功能解說（依名稱推定）：ProtoOA取消訂閱LiveK線回應
| Field | Type | Label | 中文解說(依名稱推定) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | 類型 |
| ctidTraderAccountId | int64 | optional | 交易帳戶帳戶ID |

### ProtoOAUnsubscribeSpotsReq
中文功能解說（依名稱推定）：ProtoOA取消訂閱Spots請求
| Field | Type | Label | 中文解說(依名稱推定) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | 類型 |
| ctidTraderAccountId | int64 | optional | 交易帳戶帳戶ID |
| symbolId | int64 | repeated | ID |

### ProtoOAUnsubscribeSpotsRes
中文功能解說（依名稱推定）：ProtoOA取消訂閱Spots回應
| Field | Type | Label | 中文解說(依名稱推定) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | 類型 |
| ctidTraderAccountId | int64 | optional | 交易帳戶帳戶ID |

### ProtoOAVersionReq
中文功能解說（依名稱推定）：ProtoOAVersion請求
| Field | Type | Label | 中文解說(依名稱推定) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | 類型 |

### ProtoOAVersionRes
中文功能解說（依名稱推定）：ProtoOAVersion回應
| Field | Type | Label | 中文解說(依名稱推定) |
|---|---|---|---|
| payloadType | ProtoOAPayloadType | optional | 類型 |
| version | string | optional | version |

## Open API Model Messages

### Messages

### ProtoOAArchivedSymbol
中文功能解說（依名稱推定）：ProtoOAArchived交易品種
| Field | Type | Label | 中文解說(依名稱推定) |
|---|---|---|---|
| symbolId | int64 | optional | ID |
| name | string | optional | name |
| utcLastUpdateTimestamp | int64 | optional | LastUpdate時間戳 |
| description | string | optional | description |

### ProtoOAAsset
中文功能解說（依名稱推定）：ProtoOA資產
| Field | Type | Label | 中文解說(依名稱推定) |
|---|---|---|---|
| assetId | int64 | optional | ID |
| name | string | optional | name |
| displayName | string | optional | Name |
| digits | int32 | optional | digits |

### ProtoOAAssetClass
中文功能解說（依名稱推定）：ProtoOA資產Class
| Field | Type | Label | 中文解說(依名稱推定) |
|---|---|---|---|
| id | int64 | optional | id |
| name | string | optional | name |

### ProtoOABonusDepositWithdraw
中文功能解說（依名稱推定）：ProtoOABonusDepositWithdraw
| Field | Type | Label | 中文解說(依名稱推定) |
|---|---|---|---|
| operationType | ProtoOAChangeBonusType | optional | 類型 |
| bonusHistoryId | int64 | optional | 歷史ID |
| managerBonus | int64 | optional | Bonus |
| managerDelta | int64 | optional | Delta |
| ibBonus | int64 | optional | Bonus |
| ibDelta | int64 | optional | Delta |
| changeBonusTimestamp | int64 | optional | Bonus時間戳 |
| externalNote | string | optional | Note |
| introducingBrokerId | int64 | optional | BrokerID |
| moneyDigits | uint32 | optional | Digits |

### ProtoOAClosePositionDetail
中文功能解說（依名稱推定）：ProtoOA收盤持倉Detail
| Field | Type | Label | 中文解說(依名稱推定) |
|---|---|---|---|
| entryPrice | double | optional | 價格 |
| grossProfit | int64 | optional | 獲利 |
| swap | int64 | optional | swap |
| commission | int64 | optional | commission |
| balance | int64 | optional | balance |
| quoteToDepositConversionRate | double | optional | ToDepositConversionRate |
| closedVolume | int64 | optional | 成交量 |
| balanceVersion | int64 | optional | Version |
| moneyDigits | uint32 | optional | Digits |
| pnlConversionFee | int64 | optional | Conversion費用 |

### ProtoOACtidProfile
中文功能解說（依名稱推定）：ProtoOACtidProfile
| Field | Type | Label | 中文解說(依名稱推定) |
|---|---|---|---|
| userId | int64 | optional | ID |

### ProtoOACtidTraderAccount
中文功能解說（依名稱推定）：ProtoOACtid交易帳戶帳戶
| Field | Type | Label | 中文解說(依名稱推定) |
|---|---|---|---|
| ctidTraderAccountId | uint64 | optional | 交易帳戶帳戶ID |
| isLive | bool | optional | Live |
| traderLogin | int64 | optional | Login |
| lastClosingDealTimestamp | int64 | optional | Closing成交時間戳 |
| lastBalanceUpdateTimestamp | int64 | optional | BalanceUpdate時間戳 |

### ProtoOADeal
中文功能解說（依名稱推定）：ProtoOA成交
| Field | Type | Label | 中文解說(依名稱推定) |
|---|---|---|---|
| dealId | int64 | optional | ID |
| orderId | int64 | optional | ID |
| positionId | int64 | optional | ID |
| volume | int64 | optional | volume |
| filledVolume | int64 | optional | 成交量 |
| symbolId | int64 | optional | ID |
| createTimestamp | int64 | optional | 時間戳 |
| executionTimestamp | int64 | optional | 時間戳 |
| utcLastUpdateTimestamp | int64 | optional | LastUpdate時間戳 |
| executionPrice | double | optional | 價格 |
| tradeSide | ProtoOATradeSide | optional | 方向 |
| dealStatus | ProtoOADealStatus | optional | 狀態 |
| marginRate | double | optional | Rate |
| commission | int64 | optional | commission |
| baseToUsdConversionRate | double | optional | ToUsdConversionRate |
| closePositionDetail | ProtoOAClosePositionDetail | optional | 持倉Detail |
| moneyDigits | uint32 | optional | Digits |

### ProtoOADealOffset
中文功能解說（依名稱推定）：ProtoOA成交Offset
| Field | Type | Label | 中文解說(依名稱推定) |
|---|---|---|---|
| dealId | int64 | optional | ID |
| volume | int64 | optional | volume |
| executionTimestamp | int64 | optional | 時間戳 |
| executionPrice | double | optional | 價格 |

### ProtoOADepositWithdraw
中文功能解說（依名稱推定）：ProtoOADepositWithdraw
| Field | Type | Label | 中文解說(依名稱推定) |
|---|---|---|---|
| operationType | ProtoOAChangeBalanceType | optional | 類型 |
| balanceHistoryId | int64 | optional | 歷史ID |
| balance | int64 | optional | balance |
| delta | int64 | optional | delta |
| changeBalanceTimestamp | int64 | optional | Balance時間戳 |
| externalNote | string | optional | Note |
| balanceVersion | int64 | optional | Version |
| equity | int64 | optional | equity |
| moneyDigits | uint32 | optional | Digits |

### ProtoOADepthQuote
中文功能解說（依名稱推定）：ProtoOA深度Quote
| Field | Type | Label | 中文解說(依名稱推定) |
|---|---|---|---|
| id | uint64 | optional | id |
| size | uint64 | optional | size |
| bid | uint64 | optional | bid |
| ask | uint64 | optional | ask |

### ProtoOADynamicLeverage
中文功能解說（依名稱推定）：ProtoOA動態槓桿
| Field | Type | Label | 中文解說(依名稱推定) |
|---|---|---|---|
| leverageId | int64 | optional | ID |
| tiers | ProtoOADynamicLeverageTier | repeated | tiers |

### ProtoOADynamicLeverageTier
中文功能解說（依名稱推定）：ProtoOA動態槓桿Tier
| Field | Type | Label | 中文解說(依名稱推定) |
|---|---|---|---|
| volume | int64 | optional | volume |
| leverage | int64 | optional | leverage |

### ProtoOAExpectedMargin
中文功能解說（依名稱推定）：ProtoOA預估保證金
| Field | Type | Label | 中文解說(依名稱推定) |
|---|---|---|---|
| volume | int64 | optional | volume |
| buyMargin | int64 | optional | 保證金 |
| sellMargin | int64 | optional | 保證金 |

### ProtoOAHoliday
中文功能解說（依名稱推定）：ProtoOAHoliday
| Field | Type | Label | 中文解說(依名稱推定) |
|---|---|---|---|
| holidayId | int64 | optional | ID |
| name | string | optional | name |
| description | string | optional | description |
| scheduleTimeZone | string | optional | 時間Zone |
| holidayDate | int64 | optional | Date |
| isRecurring | bool | optional | Recurring |
| startSecond | int32 | optional | Second |
| endSecond | int32 | optional | Second |

### ProtoOAInterval
中文功能解說（依名稱推定）：ProtoOA間隔
| Field | Type | Label | 中文解說(依名稱推定) |
|---|---|---|---|
| startSecond | uint32 | optional | Second |
| endSecond | uint32 | optional | Second |

### ProtoOALightSymbol
中文功能解說（依名稱推定）：ProtoOALight交易品種
| Field | Type | Label | 中文解說(依名稱推定) |
|---|---|---|---|
| symbolId | int64 | optional | ID |
| symbolName | string | optional | Name |
| enabled | bool | optional | enabled |
| baseAssetId | int64 | optional | 資產ID |
| quoteAssetId | int64 | optional | 資產ID |
| symbolCategoryId | int64 | optional | CategoryID |
| description | string | optional | description |

### ProtoOAMarginCall
中文功能解說（依名稱推定）：ProtoOA保證金Call
| Field | Type | Label | 中文解說(依名稱推定) |
|---|---|---|---|
| marginCallType | ProtoOANotificationType | optional | Call類型 |
| marginLevelThreshold | double | optional | LevelThreshold |
| utcLastUpdateTimestamp | int64 | optional | LastUpdate時間戳 |

### ProtoOAOrder
中文功能解說（依名稱推定）：ProtoOA訂單
| Field | Type | Label | 中文解說(依名稱推定) |
|---|---|---|---|
| orderId | int64 | optional | ID |
| tradeData | ProtoOATradeData | optional | Data |
| orderType | ProtoOAOrderType | optional | 類型 |
| orderStatus | ProtoOAOrderStatus | optional | 狀態 |
| expirationTimestamp | int64 | optional | 時間戳 |
| executionPrice | double | optional | 價格 |
| executedVolume | int64 | optional | 成交量 |
| utcLastUpdateTimestamp | int64 | optional | LastUpdate時間戳 |
| baseSlippagePrice | double | optional | 滑點價格 |
| slippageInPoints | int64 | optional | InPoints |
| closingOrder | bool | optional | 訂單 |
| limitPrice | double | optional | 價格 |
| stopPrice | double | optional | 價格 |
| stopLoss | double | optional | 虧損 |
| takeProfit | double | optional | 獲利 |
| clientOrderId | string | optional | 訂單ID |
| timeInForce | ProtoOATimeInForce | optional | InForce |
| positionId | int64 | optional | ID |
| relativeStopLoss | int64 | optional | 停損虧損 |
| relativeTakeProfit | int64 | optional | 停利獲利 |
| isStopOut | bool | optional | 停損Out |
| trailingStopLoss | bool | optional | 停損虧損 |
| stopTriggerMethod | ProtoOAOrderTriggerMethod | optional | TriggerMethod |

### ProtoOAPosition
中文功能解說（依名稱推定）：ProtoOA持倉
| Field | Type | Label | 中文解說(依名稱推定) |
|---|---|---|---|
| positionId | int64 | optional | ID |
| tradeData | ProtoOATradeData | optional | Data |
| positionStatus | ProtoOAPositionStatus | optional | 狀態 |
| swap | int64 | optional | swap |
| price | double | optional | price |
| stopLoss | double | optional | 虧損 |
| takeProfit | double | optional | 獲利 |
| utcLastUpdateTimestamp | int64 | optional | LastUpdate時間戳 |
| commission | int64 | optional | commission |
| marginRate | double | optional | Rate |
| mirroringCommission | int64 | optional | Commission |
| guaranteedStopLoss | bool | optional | 停損虧損 |
| usedMargin | uint64 | optional | 保證金 |
| stopLossTriggerMethod | ProtoOAOrderTriggerMethod | optional | 虧損TriggerMethod |
| moneyDigits | uint32 | optional | Digits |
| trailingStopLoss | bool | optional | 停損虧損 |

### ProtoOAPositionUnrealizedPnL
中文功能解說（依名稱推定）：ProtoOA持倉UnrealizedPnL
| Field | Type | Label | 中文解說(依名稱推定) |
|---|---|---|---|
| positionId | int64 | optional | ID |
| grossUnrealizedPnL | int64 | optional | UnrealizedPnL |
| netUnrealizedPnL | int32 | optional | UnrealizedPnL |

### ProtoOASymbol
中文功能解說（依名稱推定）：ProtoOA交易品種
| Field | Type | Label | 中文解說(依名稱推定) |
|---|---|---|---|
| symbolId | int64 | optional | ID |
| digits | int32 | optional | digits |
| pipPosition | int32 | optional | 持倉 |
| enableShortSelling | bool | optional | ShortSelling |
| guaranteedStopLoss | bool | optional | 停損虧損 |
| swapRollover3Days | ProtoOADayOfWeek | optional | Rollover3Days |
| swapLong | double | optional | Long |
| swapShort | double | optional | Short |
| maxVolume | int64 | optional | 成交量 |
| minVolume | int64 | optional | 成交量 |
| stepVolume | int64 | optional | 成交量 |
| maxExposure | uint64 | optional | Exposure |
| schedule | ProtoOAInterval | repeated | schedule |
| commission | int64 | optional | commission |
| commissionType | ProtoOACommissionType | optional | 類型 |
| slDistance | uint32 | optional | Distance |
| tpDistance | uint32 | optional | Distance |
| gslDistance | uint32 | optional | Distance |
| gslCharge | int64 | optional | Charge |
| distanceSetIn | ProtoOASymbolDistanceType | optional | SetIn |
| minCommission | int64 | optional | Commission |
| minCommissionType | ProtoOAMinCommissionType | optional | Commission類型 |
| minCommissionAsset | string | optional | Commission資產 |
| rolloverCommission | int64 | optional | Commission |
| skipRolloverDays | int32 | optional | RolloverDays |
| scheduleTimeZone | string | optional | 時間Zone |
| tradingMode | ProtoOATradingMode | optional | Mode |
| rolloverCommission3Days | ProtoOADayOfWeek | optional | Commission3Days |
| swapCalculationType | ProtoOASwapCalculationType | optional | Calculation類型 |
| lotSize | int64 | optional | Size |
| preciseTradingCommissionRate | int64 | optional | TradingCommissionRate |
| preciseMinCommission | int64 | optional | 最小Commission |
| holiday | ProtoOAHoliday | repeated | holiday |
| pnlConversionFeeRate | int32 | optional | Conversion費用Rate |
| leverageId | int64 | optional | ID |
| swapPeriod | int32 | optional | 週期 |
| swapTime | int32 | optional | 時間 |
| skipSWAPPeriods | int32 | optional | SWAPPeriods |
| chargeSwapAtWeekends | bool | optional | SwapAtWeekends |

### ProtoOASymbolCategory
中文功能解說（依名稱推定）：ProtoOA交易品種Category
| Field | Type | Label | 中文解說(依名稱推定) |
|---|---|---|---|
| id | int64 | optional | id |
| assetClassId | int64 | optional | ClassID |
| name | string | optional | name |

### ProtoOATickData
中文功能解說（依名稱推定）：ProtoOATickData
| Field | Type | Label | 中文解說(依名稱推定) |
|---|---|---|---|
| timestamp | int64 | optional | timestamp |
| tick | int64 | optional | tick |

### ProtoOATradeData
中文功能解說（依名稱推定）：ProtoOA交易Data
| Field | Type | Label | 中文解說(依名稱推定) |
|---|---|---|---|
| symbolId | int64 | optional | ID |
| volume | int64 | optional | volume |
| tradeSide | ProtoOATradeSide | optional | 方向 |
| openTimestamp | int64 | optional | 時間戳 |
| label | string | optional | label |
| guaranteedStopLoss | bool | optional | 停損虧損 |
| comment | string | optional | comment |

### ProtoOATrader
中文功能解說（依名稱推定）：ProtoOA交易帳戶
| Field | Type | Label | 中文解說(依名稱推定) |
|---|---|---|---|
| ctidTraderAccountId | int64 | optional | 交易帳戶帳戶ID |
| balance | int64 | optional | balance |
| balanceVersion | int64 | optional | Version |
| managerBonus | int64 | optional | Bonus |
| ibBonus | int64 | optional | Bonus |
| nonWithdrawableBonus | int64 | optional | WithdrawableBonus |
| accessRights | ProtoOAAccessRights | optional | Rights |
| depositAssetId | int64 | optional | 資產ID |
| swapFree | bool | optional | Free |
| leverageInCents | uint32 | optional | InCents |
| totalMarginCalculationType | ProtoOATotalMarginCalculationType | optional | 保證金Calculation類型 |
| maxLeverage | uint32 | optional | 槓桿 |
| frenchRisk | bool | optional | 風險 |
| traderLogin | int64 | optional | Login |
| accountType | ProtoOAAccountType | optional | 類型 |
| brokerName | string | optional | Name |
| registrationTimestamp | int64 | optional | 時間戳 |
| isLimitedRisk | bool | optional | Limited風險 |
| limitedRiskMarginCalculationStrategy | ProtoOALimitedRiskMarginCalculationStrategy | optional | 風險保證金CalculationStrategy |
| moneyDigits | uint32 | optional | Digits |

### ProtoOATrendbar
中文功能解說（依名稱推定）：ProtoOAK線
| Field | Type | Label | 中文解說(依名稱推定) |
|---|---|---|---|
| volume | int64 | optional | volume |
| period | ProtoOATrendbarPeriod | optional | period |
| low | int64 | optional | low |
| deltaOpen | uint64 | optional | 開盤 |
| deltaClose | uint64 | optional | 收盤 |
| deltaHigh | uint64 | optional | 最高 |
| utcTimestampInMinutes | uint32 | optional | 時間戳InMinutes |

### Enums

### ProtoOAAccessRights
中文功能解說（依名稱推定）：ProtoOAAccessRights
| Name | Value | 中文解說(依名稱推定) |
|---|---|---|
| FULL_ACCESS | 0 | FULLACCESS |
| CLOSE_ONLY | 1 | CLOSEONLY |
| NO_TRADING | 2 | NOTRADING |
| NO_LOGIN | 3 | NOLOGIN |

### ProtoOAAccountType
中文功能解說（依名稱推定）：ProtoOA帳戶類型
| Name | Value | 中文解說(依名稱推定) |
|---|---|---|
| HEDGED | 0 | HEDGED |
| NETTED | 1 | NETTED |
| SPREAD_BETTING | 2 | SPREADBETTING |

### ProtoOAChangeBalanceType
中文功能解說（依名稱推定）：ProtoOAChangeBalance類型
| Name | Value | 中文解說(依名稱推定) |
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
中文功能解說（依名稱推定）：ProtoOAChangeBonus類型
| Name | Value | 中文解說(依名稱推定) |
|---|---|---|
| BONUS_DEPOSIT | 0 | BONUSDEPOSIT |
| BONUS_WITHDRAW | 1 | BONUSWITHDRAW |

### ProtoOAClientPermissionScope
中文功能解說（依名稱推定）：ProtoOAClientPermissionScope
| Name | Value | 中文解說(依名稱推定) |
|---|---|---|
| SCOPE_VIEW | 0 | SCOPEVIEW |
| SCOPE_TRADE | 1 | SCOPETRADE |

### ProtoOACommissionType
中文功能解說（依名稱推定）：ProtoOACommission類型
| Name | Value | 中文解說(依名稱推定) |
|---|---|---|
| USD_PER_MILLION_USD | 1 | USDPERMILLIONUSD |
| USD_PER_LOT | 2 | USDPERLOT |
| PERCENTAGE_OF_VALUE | 3 | PERCENTAGEOFVALUE |
| QUOTE_CCY_PER_LOT | 4 | QUOTECCYPERLOT |

### ProtoOADayOfWeek
中文功能解說（依名稱推定）：ProtoOADayOfWeek
| Name | Value | 中文解說(依名稱推定) |
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
中文功能解說（依名稱推定）：ProtoOA成交狀態
| Name | Value | 中文解說(依名稱推定) |
|---|---|---|
| FILLED | 2 | FILLED |
| PARTIALLY_FILLED | 3 | PARTIALLYFILLED |
| REJECTED | 4 | REJECTED |
| INTERNALLY_REJECTED | 5 | INTERNALLYREJECTED |
| ERROR | 6 | ERROR |
| MISSED | 7 | MISSED |

### ProtoOAErrorCode
中文功能解說（依名稱推定）：ProtoOA錯誤Code
| Name | Value | 中文解說(依名稱推定) |
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
中文功能解說（依名稱推定）：ProtoOAExecution類型
| Name | Value | 中文解說(依名稱推定) |
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
中文功能解說（依名稱推定）：ProtoOALimited風險保證金CalculationStrategy
| Name | Value | 中文解說(依名稱推定) |
|---|---|---|
| ACCORDING_TO_LEVERAGE | 0 | ACCORDINGTOLEVERAGE |
| ACCORDING_TO_GSL | 1 | ACCORDINGTOGSL |
| ACCORDING_TO_GSL_AND_LEVERAGE | 2 | ACCORDINGTOGSLANDLEVERAGE |

### ProtoOAMinCommissionType
中文功能解說（依名稱推定）：ProtoOA最小Commission類型
| Name | Value | 中文解說(依名稱推定) |
|---|---|---|
| CURRENCY | 1 | CURRENCY |
| QUOTE_CURRENCY | 2 | QUOTECURRENCY |

### ProtoOANotificationType
中文功能解說（依名稱推定）：ProtoOANotification類型
| Name | Value | 中文解說(依名稱推定) |
|---|---|---|
| MARGIN_LEVEL_THRESHOLD_1 | 61 | MARGINLEVELTHRESHOLD |
| MARGIN_LEVEL_THRESHOLD_2 | 62 | MARGINLEVELTHRESHOLD |
| MARGIN_LEVEL_THRESHOLD_3 | 63 | MARGINLEVELTHRESHOLD |

### ProtoOAOrderStatus
中文功能解說（依名稱推定）：ProtoOA訂單狀態
| Name | Value | 中文解說(依名稱推定) |
|---|---|---|
| ORDER_STATUS_ACCEPTED | 1 | ORDERSTATUSACCEPTED |
| ORDER_STATUS_FILLED | 2 | ORDERSTATUSFILLED |
| ORDER_STATUS_REJECTED | 3 | ORDERSTATUSREJECTED |
| ORDER_STATUS_EXPIRED | 4 | ORDERSTATUSEXPIRED |
| ORDER_STATUS_CANCELLED | 5 | ORDERSTATUSCANCELLED |

### ProtoOAOrderTriggerMethod
中文功能解說（依名稱推定）：ProtoOA訂單TriggerMethod
| Name | Value | 中文解說(依名稱推定) |
|---|---|---|
| TRADE | 1 | TRADE |
| OPPOSITE | 2 | OPPOSITE |
| DOUBLE_TRADE | 3 | DOUBLETRADE |
| DOUBLE_OPPOSITE | 4 | DOUBLEOPPOSITE |

### ProtoOAOrderType
中文功能解說（依名稱推定）：ProtoOA訂單類型
| Name | Value | 中文解說(依名稱推定) |
|---|---|---|
| MARKET | 1 | MARKET |
| LIMIT | 2 | LIMIT |
| STOP | 3 | STOP |
| STOP_LOSS_TAKE_PROFIT | 4 | STOPLOSSTAKEPROFIT |
| MARKET_RANGE | 5 | MARKETRANGE |
| STOP_LIMIT | 6 | STOPLIMIT |

### ProtoOAPayloadType
中文功能解說（依名稱推定）：ProtoOAPayload類型
| Name | Value | 中文解說(依名稱推定) |
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
中文功能解說（依名稱推定）：ProtoOA持倉狀態
| Name | Value | 中文解說(依名稱推定) |
|---|---|---|
| POSITION_STATUS_OPEN | 1 | POSITIONSTATUSOPEN |
| POSITION_STATUS_CLOSED | 2 | POSITIONSTATUSCLOSED |
| POSITION_STATUS_CREATED | 3 | POSITIONSTATUSCREATED |
| POSITION_STATUS_ERROR | 4 | POSITIONSTATUSERROR |

### ProtoOAQuoteType
中文功能解說（依名稱推定）：ProtoOAQuote類型
| Name | Value | 中文解說(依名稱推定) |
|---|---|---|
| BID | 1 | BID |
| ASK | 2 | ASK |

### ProtoOASwapCalculationType
中文功能解說（依名稱推定）：ProtoOASwapCalculation類型
| Name | Value | 中文解說(依名稱推定) |
|---|---|---|
| PIPS | 0 | PIPS |
| PERCENTAGE | 1 | PERCENTAGE |

### ProtoOASymbolDistanceType
中文功能解說（依名稱推定）：ProtoOA交易品種Distance類型
| Name | Value | 中文解說(依名稱推定) |
|---|---|---|
| SYMBOL_DISTANCE_IN_POINTS | 1 | SYMBOLDISTANCEINPOINTS |
| SYMBOL_DISTANCE_IN_PERCENTAGE | 2 | SYMBOLDISTANCEINPERCENTAGE |

### ProtoOATimeInForce
中文功能解說（依名稱推定）：ProtoOA時間InForce
| Name | Value | 中文解說(依名稱推定) |
|---|---|---|
| GOOD_TILL_DATE | 1 | GOODTILLDATE |
| GOOD_TILL_CANCEL | 2 | GOODTILLCANCEL |
| IMMEDIATE_OR_CANCEL | 3 | IMMEDIATEORCANCEL |
| FILL_OR_KILL | 4 | FILLORKILL |
| MARKET_ON_OPEN | 5 | MARKETONOPEN |

### ProtoOATotalMarginCalculationType
中文功能解說（依名稱推定）：ProtoOATotal保證金Calculation類型
| Name | Value | 中文解說(依名稱推定) |
|---|---|---|
| MAX | 0 | MAX |
| SUM | 1 | SUM |
| NET | 2 | NET |

### ProtoOATradeSide
中文功能解說（依名稱推定）：ProtoOA交易方向
| Name | Value | 中文解說(依名稱推定) |
|---|---|---|
| BUY | 1 | BUY |
| SELL | 2 | SELL |

### ProtoOATradingMode
中文功能解說（依名稱推定）：ProtoOATradingMode
| Name | Value | 中文解說(依名稱推定) |
|---|---|---|
| ENABLED | 0 | ENABLED |
| DISABLED_WITHOUT_PENDINGS_EXECUTION | 1 | DISABLEDWITHOUTPENDINGSEXECUTION |
| DISABLED_WITH_PENDINGS_EXECUTION | 2 | DISABLEDWITHPENDINGSEXECUTION |
| CLOSE_ONLY_MODE | 3 | CLOSEONLYMODE |

### ProtoOATrendbarPeriod
中文功能解說（依名稱推定）：ProtoOAK線週期
| Name | Value | 中文解說(依名稱推定) |
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

### Messages

### ProtoErrorRes
中文功能解說（依名稱推定）：Proto錯誤回應
| Field | Type | Label | 中文解說(依名稱推定) |
|---|---|---|---|
| payloadType | ProtoPayloadType | optional | 類型 |
| errorCode | string | optional | Code |
| description | string | optional | description |
| maintenanceEndTimestamp | uint64 | optional | End時間戳 |

### ProtoHeartbeatEvent
中文功能解說（依名稱推定）：ProtoHeartbeat事件
| Field | Type | Label | 中文解說(依名稱推定) |
|---|---|---|---|
| payloadType | ProtoPayloadType | optional | 類型 |

### ProtoMessage
中文功能解說（依名稱推定）：ProtoMessage
| Field | Type | Label | 中文解說(依名稱推定) |
|---|---|---|---|
| payloadType | uint32 | optional | 類型 |
| payload | bytes | optional | payload |
| clientMsgId | string | optional | MsgID |

## Common Model Messages

### Enums

### ProtoErrorCode
中文功能解說（依名稱推定）：Proto錯誤Code
| Name | Value | 中文解說(依名稱推定) |
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
中文功能解說（依名稱推定）：ProtoPayload類型
| Name | Value | 中文解說(依名稱推定) |
|---|---|---|
| PROTO_MESSAGE | 5 | PROTOMESSAGE |
| ERROR_RES | 50 | ERRORRES |
| HEARTBEAT_EVENT | 51 | HEARTBEATEVENT |

