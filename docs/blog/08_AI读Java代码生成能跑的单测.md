# AI 读 Java 业务代码,生成能编译能跑的单测——真 AI,不是套模板

> 前面几篇讲的是黑盒(接口测试)。这篇讲白盒:**让 AI 读你的 Java 方法,生成 JUnit 单测。**
> 市面上"AI 生成单测"很多,但大多是套模板拼骨架、断言是空的。这篇讲怎么让它生成**能编译、能跑、断言是真的**的单测——以及怎么验证它真懂了逻辑。

---

## 一、"AI 生成单测"的陷阱:看着有,其实空

你让工具生成单测,常得到这种:

```java
@Test
void testGetHeadCode() {
    // TODO: arrange
    HeadCodeEnum result = controller.getHeadCodeEnumByRespCode(list);
    assertNotNull(result);   // ← 断言是废的,测了个寂寞
}
```

骨架有了,但 `assertNotNull` 这种断言等于没测——它不关心逻辑对不对,只关心"没崩"。**这种单测给你虚假的覆盖率,是负资产。**

真正有用的单测,断言必须**咬住业务逻辑**:全成功该返回 SUCCESS、全失败该返回 FAIL、部分成功该返回 PART_SUCCESS。要生成这种,AI 必须**真读懂方法在干什么**。

---

## 二、让 AI 真读懂:喂源码 + 明确要求

目标方法(价格中心真实代码,判断整体响应状态):

```java
public HeadCodeEnum getHeadCodeEnumByRespCode(List<PullPriceX5Resp> respList) {
    Map<Boolean,List<PullPriceX5Resp>> m = respList.stream()
        .collect(partitioningBy(r -> SUCCESS.getCode().equals(r.getCode())));
    if (m.get(true).size() == respList.size()) return SUCCESS;   // 全成功
    else if (m.get(false).size() == respList.size()) return FAIL; // 全失败
    else return PART_SUCCESS;                                     // 部分
}
```

我把**方法源码 + 依赖枚举 + 明确的测试要求**打包成 spec,喂给本机的 codex(GPT-5.5):

```python
prompt = f"""为下面的方法生成JUnit5单测,只输出Java代码。
覆盖:全成功→SUCCESS / 全失败→FAIL / 部分→PART_SUCCESS / 空列表边界。
断言必须真实(assertEquals具体枚举),不许用assertNotNull占位。
方法:{method_source}
枚举:{enum_context}"""
```

**关键:调本机 codex CLI,不是套模板。** 它会真读这段流式逻辑,推断出 code=0 表示成功、要覆盖三种分支。

---

## 三、它生成了什么(真实产出,编译跑通)

> 📸 配图位置:此处配一张 codex 生成单测 + Maven 编译跑通的真实截图

codex 生成了 83 行 `ApiX5ControllerTest.java`,节选:

```java
@Test
void allSuccess_shouldReturnSUCCESS() {
    List<PullPriceX5Resp> list = Arrays.asList(resp(0), resp(0));  // code=0 全成功
    assertEquals(HeadCodeEnum.SUCCESS, controller.getHeadCodeEnumByRespCode(list));
}
@Test
void allFail_shouldReturnFAIL() {
    List<PullPriceX5Resp> list = Arrays.asList(resp(-1), resp(-1));
    assertEquals(HeadCodeEnum.FAIL, controller.getHeadCodeEnumByRespCode(list));
}
@Test
void partial_shouldReturnPART_SUCCESS() {
    List<PullPriceX5Resp> list = Arrays.asList(resp(0), resp(-1));  // 一成一败
    assertEquals(HeadCodeEnum.PART_SUCCESS, controller.getHeadCodeEnumByRespCode(list));
}
```

**断言是真的**:`assertEquals(SUCCESS, ...)` 咬住了具体枚举,不是占位符。而且它**主动覆盖了三个分支 + 空列表边界**——说明它真读懂了 `partitioningBy` 那段逻辑。

编译运行:**6/6 通过。** 这不是套模板,是真理解。

---

## 四、怎么保证"真懂"而不是"蒙对"

我不轻信"跑通了就是对的"。验证方式:

1. **改逻辑,看它是否跟着变** —— 换个方法喂进去,它生成的断言跟着变,说明是理解不是背模板
2. **看它有没有覆盖边界** —— 空列表这个边界它主动测了(`partitioningBy` 空集时 `m.get(true).size()==0==size()` 返回SUCCESS,是个隐藏行为),说明它推了逻辑
3. **编译 + 运行双验证** —— 光生成不算,得真能编译、真能跑过

**这三关过了,才敢说"AI 真会写这个单测"。**

---

## 五、复现

```bash
python tools/codegen/java_unit_test_generate.py \
    --spec unit_test_spec.json --out XxxTest.java
# 需本机装 codex CLI
```

spec 里放目标方法源码 + 依赖上下文,换成你的方法即可。

---

## 六、诚实边界

- 依赖本机 codex CLI(GPT-5.5),有调用耗时(几十秒)和偶发波动。
- 目前对"纯逻辑方法"效果最好;重依赖注入的方法,还需喂更多 mock 上下文。
- 生成后必须编译+运行验证,不能盲信——**AI 生成 + 机器验证,缺一不可。**

---

> **一句话**:AI 生成单测的价值不在"生成得多",在"断言是不是真的咬住了逻辑"。让它真读源码、明确要求真断言、再用编译运行验证——这才是白盒 AI 测试该有的样子。
