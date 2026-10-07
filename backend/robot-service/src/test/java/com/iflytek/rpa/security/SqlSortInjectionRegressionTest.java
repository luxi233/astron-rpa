package com.iflytek.rpa.security;

import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import org.junit.jupiter.api.Test;

class SqlSortInjectionRegressionTest {

    @Test
    void userControlledSortColumnsAreNotSubstitutedIntoSql() throws IOException {
        assertSortIsAllowlisted("com/iflytek/rpa/task/dao/ScheduleTaskDao.xml");
        assertSortIsAllowlisted("com/iflytek/rpa/robot/dao/RobotExecuteRecordDao.xml");
        assertSortIsAllowlisted("com/iflytek/rpa/market/dao/AppMarketUserDao.xml");
    }

    private void assertSortIsAllowlisted(String relativePath) throws IOException {
        Path mapper = Paths.get("src/main/java").resolve(relativePath);
        String xml = new String(Files.readAllBytes(mapper), StandardCharsets.UTF_8);

        assertFalse(xml.contains("${entity.sortBy}"), relativePath);
        assertTrue(xml.contains("order by"), relativePath);
    }
}
