package com.iflytek.rpa.auth.sp.casdoor.utils;

/** Utility methods for treating user input as literal text in SQL LIKE patterns. */
public final class SqlLikeUtils {

    private SqlLikeUtils() {}

    public static String escapePattern(String value) {
        if (value == null) {
            return null;
        }
        return value.trim().replace("!", "!!").replace("%", "!%").replace("_", "!_");
    }
}
