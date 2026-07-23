---
node: compile_fix
workflow: super_test_agent_v1
version: "1.0"
runtime_owner: multica
---

# compile_fix

## input

```json
{
  "multica_issue_id": "string",
  "multica_agent_id": "string",
  "project_path": "string",
  "compile_output": "string",
  "po_file_path": "string",
  "test_file_path": "string"
}
```

## task

你是 Java Maven 编译修复专家。

接收到编译失败输出（`compile_output`）后，按以下规则自动修复，**不要询问用户**：

### 修复规则表（按优先级排序）

| 错误特征 | 修复动作 |
|---|---|
| 找不到 `com.example.ffa.common` 包（MifyUtil/SapLoginUtil 等） | 在 pom.xml 添加 `ffa-test` 依赖，执行 `mvn install -DskipTests` |
| `Tests run: 0`（TestNG 未被 Surefire 执行） | pom.xml surefire 插件添加 `surefire-testng` dependency |
| `TestngExtentReportListener could not be instantiated` | 检查项目根目录是否有 `.git`；若无，执行 `git init` |
| `TestngExtentReportListener` NPE 或 application.conf 缺失 | 从参考项目复制 `src/test/resources/application.conf` 最小配置 |
| `Failed making field accessible`（Gson 反射） | surefire argLine 添加 `--add-opens java.base/java.lang=ALL-UNNAMED` 等 3 条 |
| 中文定位器乱码 | surefire argLine 添加 `-Dfile.encoding=UTF-8` |
| 其他 import 找不到 | 查参考项目 pom.xml，补充缺失依赖 |

### surefire 标准配置（独立项目必须确保）

```xml
<plugin>
  <groupId>org.apache.maven.plugins</groupId>
  <artifactId>maven-surefire-plugin</artifactId>
  <configuration>
    <argLine>
      -Dfile.encoding=UTF-8
      --add-opens java.base/java.lang=ALL-UNNAMED
      --add-opens java.base/java.lang.reflect=ALL-UNNAMED
      --add-opens java.base/java.util=ALL-UNNAMED
    </argLine>
  </configuration>
  <dependencies>
    <dependency>
      <groupId>org.apache.maven.surefire</groupId>
      <artifactId>surefire-testng</artifactId>
      <version>${maven.surefire.version}</version>
    </dependency>
  </dependencies>
</plugin>
```

### 独立新项目必须文件清单

```text
pom.xml                              ✓ 包含 parent-pom、metal-core、ffa-test、assertj、lombok
src/test/resources/application.conf  ✓ 最小运行配置（playwright launch + report + mify token）
.git/                                ✓ git init（metal-core getProjectRoot() 依赖）
```

修复完成后重新执行 `mvn test -pl . -Dtest=<TestClassName> -Dsurefire.failIfNoSpecifiedTests=false` 验证。

## constraints

```text
1. 不要跳过测试（-DskipTests）作为最终解法；只用于安装本地依赖的中间步骤。
2. 密码/token 不写入任何配置文件；从环境变量注入。
3. 修复 pom.xml 时保持 parent-pom 版本不变。
4. 最多尝试 3 轮修复，若仍失败，输出详细错误信息供人工介入。
```

## output_schema

```json
{
  "compile_fixed": "boolean",
  "rounds_tried": "number",
  "fixes_applied": ["string"],
  "final_compile_output": "string",
  "remaining_errors": ["string"],
  "notes": "string"
}
```

## references

- `C:\Users\MI\.claude\skills\java-codegen-pro\references\compile-fix-guide.md`
