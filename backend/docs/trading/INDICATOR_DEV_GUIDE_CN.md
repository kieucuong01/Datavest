# QuantDinger 指标开发指南

> 适用范围：当前图表 Indicator 契约

QuantDinger Indicator 是在 Indicator IDE 中运行的 Python 图表程序。它读取当前 K 线 DataFrame，计算对齐的序列，并通过 `output` 返回曲线、标记和图层。

最重要的边界是：**Indicator 只用于图表分析。** 它不能回测、读取账户、管理持仓或执行交易。需要验证一个想法时，应把视觉信号转换为 Strategy API V2 策略，再单独校验和回测。

## 1. 最小示例

```python
my_indicator_name = "Close Line"
my_indicator_description = "Displays close price on the chart."

df = df.copy()
close_line = [None if pd.isna(value) else float(value) for value in df["close"]]

output = {
    "name": my_indicator_name,
    "plots": [{
        "name": "Close",
        "data": close_line,
        "color": "#3B82F6",
        "type": "line",
        "overlay": True,
    }],
    "signals": [],
    "layers": [],
}
```

## 2. 输入与输出

运行时提供 `df`、`params`、`pd` 和 `np`。程序必须设置 `output` 字典：

- `plots`：与 `df` 等长的曲线或柱状序列；
- `signals`：稀疏的视觉事件标记；
- `layers`：区间、线和标签等图表对象；
- 缺失点使用 `None`，不能输出 NaN 或无穷值。

先执行 `df = df.copy()`，不要改名或删除必要的 OHLCV 列，也不要假设存在 `time` 列。

## 3. 参数

```python
# @param period int 20 Calculation period range=5:60:5
period = int(params.get("period", 20))
```

参数只控制计算和显示。不要声明账户、仓位、杠杆或交易设置。

## 4. 信号语义

`output["signals"]` 中的 `buy`/`sell` 只控制图表标记方向，不会产生订单。优先输出一次性事件，而不是在条件持续成立时重复标记。

```python
condition = fast > slow
event = condition.fillna(False) & ~condition.shift(1, fill_value=False)
marks = [float(df["low"].iloc[i]) if bool(event.iloc[i]) else None for i in range(len(df))]
```

从 Indicator 转换为策略时，必须明确视觉事件对应入场、退出还是警告，不能仅凭标记名称推断交易含义。

## 5. Pine 迁移边界

迁移 Pine 指标意味着用 Python/pandas 保留常见单标的、单周期计算与视觉语义，不代表直接执行 Pine 源码。多周期请求、逐 tick 状态、表格和动态绘图生命周期不在当前契约内。

在固定 OHLCV 夹具上比较数值容差、预热区间、缺失值和事件索引。若原脚本依赖未支持能力，应记录近似方式，不能宣称完全兼容。

## 6. 验收清单

- `output` 是字典，包含 `plots` 或 `signals`；
- 每个序列长度等于 `len(df)`；
- 空值为 `None`；
- 事件不读取未来数据；
- Indicator 不导入账户、订单或外部连接模块；
- 描述不承诺收益，也不暗示已经过真实资金验证。
