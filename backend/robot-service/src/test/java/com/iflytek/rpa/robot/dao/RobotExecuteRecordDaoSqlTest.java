package com.iflytek.rpa.robot.dao;

import com.iflytek.rpa.robot.entity.dto.ExecuteRecordDto;
import org.apache.ibatis.builder.xml.XMLMapperBuilder;
import org.apache.ibatis.mapping.BoundSql;
import org.apache.ibatis.mapping.MappedStatement;
import org.apache.ibatis.session.Configuration;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;

import java.io.FileInputStream;
import java.io.InputStream;
import java.lang.reflect.Field;
import java.nio.file.Paths;
import java.util.HashMap;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * RobotExecuteRecordDao.xml 动态 SQL 单元测试(无数据库/无 Spring 上下文)。
 *
 * <p>通过 MyBatis 原生 XMLMapperBuilder 解析 mapper, 直接断言 getExecuteRecordList
 * 在不同 triggerType 取值下生成的 BoundSql, 覆盖:
 * <ul>
 *   <li>triggerType=null/空串: 不追加触发方式过滤(回归)</li>
 *   <li>triggerType=manual: task_execute_id 为空</li>
 *   <li>triggerType=task: task_execute_id 非空</li>
 *   <li>既有筛选(result/robotName)与默认排序不受影响(回归)</li>
 * </ul>
 *
 * <p>运行方式: {@code mvn test -DskipTests=false -Dtest=RobotExecuteRecordDaoSqlTest}
 * (模块 pom 默认 skipTests=true)。
 */
class RobotExecuteRecordDaoSqlTest {

    private static final String STATEMENT_ID =
            "com.iflytek.rpa.robot.dao.RobotExecuteRecordDao.getExecuteRecordList";

    private static final String MAPPER_PATH = Paths.get(
            "src", "main", "java", "com", "iflytek", "rpa", "robot", "dao", "RobotExecuteRecordDao.xml")
            .toString();

    private static Configuration configuration;

    @BeforeAll
    static void parseMapper() throws Exception {
        configuration = new Configuration();
        // resultMap 引用的实体类注册别名, 保证 XML 可完整解析
        configuration.getTypeAliasRegistry().registerAlias(
                "com.iflytek.rpa.robot.entity.RobotExecuteRecord",
                com.iflytek.rpa.robot.entity.RobotExecuteRecord.class);
        try (InputStream in = new FileInputStream(MAPPER_PATH)) {
            XMLMapperBuilder parser = new XMLMapperBuilder(
                    in, configuration, MAPPER_PATH, configuration.getSqlFragments());
            parser.parse();
        }
    }

    /** 构造与 Mapper 接口 @Param("entity") 等价的参数 Map */
    private static Map<String, Object> params(ExecuteRecordDto dto) {
        Map<String, Object> param = new HashMap<>();
        param.put("entity", dto);
        return param;
    }

    private static String boundSql(ExecuteRecordDto dto) {
        MappedStatement ms = configuration.getMappedStatement(STATEMENT_ID);
        assertNotNull(ms, "getExecuteRecordList 语句解析失败");
        BoundSql bound = ms.getBoundSql(params(dto));
        return bound.getSql().replaceAll("\\s+", " ").trim();
    }

    @Test
    void triggerTypeNullKeepsNoFilter() {
        ExecuteRecordDto dto = new ExecuteRecordDto();
        String sql = boundSql(dto);
        assertFalse(sql.contains("task_execute_id is null"), "triggerType=null 时不应过滤 manual");
        assertFalse(sql.contains("task_execute_id is not null"), "triggerType=null 时不应过滤 task");
    }

    @Test
    void triggerTypeEmptyKeepsNoFilter() {
        ExecuteRecordDto dto = new ExecuteRecordDto();
        dto.setTriggerType("");
        String sql = boundSql(dto);
        assertFalse(sql.contains("task_execute_id is null"), "triggerType='' 时不应过滤 manual");
        assertFalse(sql.contains("task_execute_id is not null"), "triggerType='' 时不应过滤 task");
    }

    @Test
    void triggerTypeManualFiltersTaskExecuteIdEmpty() {
        ExecuteRecordDto dto = new ExecuteRecordDto();
        dto.setTriggerType("manual");
        String sql = boundSql(dto);
        assertTrue(sql.contains("rer.task_execute_id is null"), "manual 应过滤 task_execute_id 为空");
        assertTrue(sql.contains("rer.task_execute_id = ''"), "manual 应包含空字符串判断");
        assertFalse(sql.contains("task_execute_id is not null"), "manual 不应包含 task 分支");
    }

    @Test
    void triggerTypeTaskFiltersTaskExecuteIdNotEmpty() {
        ExecuteRecordDto dto = new ExecuteRecordDto();
        dto.setTriggerType("task");
        String sql = boundSql(dto);
        assertTrue(sql.contains("rer.task_execute_id is not null"), "task 应过滤 task_execute_id 非空");
        assertTrue(sql.contains("rer.task_execute_id != ''"), "task 应包含非空字符串判断");
        assertFalse(sql.contains("task_execute_id is null or"), "task 不应包含 manual 分支");
    }

    @Test
    void existingResultFilterUnaffected() {
        ExecuteRecordDto dto = new ExecuteRecordDto();
        dto.setTriggerType("manual");
        dto.setResult("robotFail");
        String sql = boundSql(dto);
        assertTrue(sql.contains("rer.result = ?"), "result 筛选应保留");
    }

    @Test
    void defaultSortUnaffected() {
        ExecuteRecordDto dto = new ExecuteRecordDto();
        String sql = boundSql(dto);
        assertTrue(sql.contains("order by start_time desc"), "默认排序应保留");
    }

    /** DTO 字段与 XML 条件联动: 防止字段被删除后 XML 残留无效条件 */
    @Test
    void dtoHasTriggerTypeField() throws Exception {
        Field field = ExecuteRecordDto.class.getDeclaredField("triggerType");
        assertTrue(field.getType() == String.class, "triggerType 应为 String 类型");
    }
}
