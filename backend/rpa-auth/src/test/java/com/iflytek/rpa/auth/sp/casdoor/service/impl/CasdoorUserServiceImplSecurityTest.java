package com.iflytek.rpa.auth.sp.casdoor.service.impl;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.when;

import com.iflytek.rpa.auth.sp.casdoor.dao.CasdoorUserDao;
import com.iflytek.rpa.auth.utils.AppResponse;
import com.iflytek.rpa.auth.utils.ErrorCodeEnum;
import java.util.Collections;
import org.casbin.casdoor.entity.User;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.mock.web.MockHttpServletRequest;
import org.springframework.test.util.ReflectionTestUtils;

class CasdoorUserServiceImplSecurityTest {

    private CasdoorUserServiceImpl service;
    private CasdoorUserDao userDao;

    @BeforeEach
    void setUp() {
        service = new CasdoorUserServiceImpl();
        userDao = mock(CasdoorUserDao.class);
        ReflectionTestUtils.setField(service, "casdoorUserDao", userDao);
        ReflectionTestUtils.setField(service, "databaseName", "casdoor");
    }

    @Test
    void rejectsSearchWhenSessionHasNoTenant() {
        MockHttpServletRequest request = authenticatedRequest(null);

        AppResponse<?> response = service.searchUserByName("admin", null, request);

        assertFalse(response.ok());
        assertEquals(ErrorCodeEnum.E_NO_POWER.getCode(), response.getCode());
        verifyNoInteractions(userDao);
    }

    @Test
    void escapesWildcardBeforeTenantScopedSearch() {
        MockHttpServletRequest request = authenticatedRequest("tenant-a");
        when(userDao.searchUserByName("!%", "tenant-a", "casdoor"))
                .thenReturn(Collections.emptyList());

        AppResponse<?> response = service.searchUserByName("%", null, request);

        assertEquals(ErrorCodeEnum.S_SUCCESS.getCode(), response.getCode());
        verify(userDao).searchUserByName("!%", "tenant-a", "casdoor");
    }

    private MockHttpServletRequest authenticatedRequest(String owner) {
        MockHttpServletRequest request = new MockHttpServletRequest();
        User user = new User();
        user.owner = owner;
        request.getSession().setAttribute("user", user);
        return request;
    }
}
