package com.iflytek.rpa.auth.sp.casdoor.utils;

import static org.junit.jupiter.api.Assertions.assertEquals;

import org.junit.jupiter.api.Test;

class SqlLikeUtilsTest {

    @Test
    void escapesSqlLikeWildcardsAndEscapeCharacter() {
        assertEquals("admin!%!_team!!ops", SqlLikeUtils.escapePattern(" admin%_team!ops "));
    }
}
