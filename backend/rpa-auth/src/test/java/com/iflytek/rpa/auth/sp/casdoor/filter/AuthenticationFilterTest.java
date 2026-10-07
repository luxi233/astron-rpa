package com.iflytek.rpa.auth.sp.casdoor.filter;

import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.concurrent.atomic.AtomicBoolean;
import org.casbin.casdoor.entity.User;
import org.junit.jupiter.api.Test;
import org.springframework.mock.web.MockHttpServletRequest;
import org.springframework.mock.web.MockHttpServletResponse;

class AuthenticationFilterTest {

    private final AuthenticationFilter filter = new AuthenticationFilter();

    @Test
    void rejectsAnonymousUserSearch() throws Exception {
        MockHttpServletRequest request = new MockHttpServletRequest("GET", "/api/rpa-auth/user/search/name");
        request.setRequestURI("/api/rpa-auth/user/search/name");
        MockHttpServletResponse response = new MockHttpServletResponse();
        AtomicBoolean invoked = new AtomicBoolean(false);

        filter.doFilter(request, response, (servletRequest, servletResponse) -> invoked.set(true));

        assertFalse(invoked.get());
        assertTrue(response.getContentAsString().contains("unauthorized"));
    }

    @Test
    void keepsLoginEndpointPublic() throws Exception {
        MockHttpServletRequest request = new MockHttpServletRequest("POST", "/api/rpa-auth/login");
        request.setRequestURI("/api/rpa-auth/login");
        MockHttpServletResponse response = new MockHttpServletResponse();
        AtomicBoolean invoked = new AtomicBoolean(false);

        filter.doFilter(request, response, (servletRequest, servletResponse) -> invoked.set(true));

        assertTrue(invoked.get());
    }

    @Test
    void allowsAuthenticatedUserSearch() throws Exception {
        MockHttpServletRequest request = new MockHttpServletRequest("GET", "/api/rpa-auth/user/search/name");
        request.setRequestURI("/api/rpa-auth/user/search/name");
        request.getSession().setAttribute("user", new User());
        MockHttpServletResponse response = new MockHttpServletResponse();
        AtomicBoolean invoked = new AtomicBoolean(false);

        filter.doFilter(request, response, (servletRequest, servletResponse) -> invoked.set(true));

        assertTrue(invoked.get());
    }
}
