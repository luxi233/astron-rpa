package com.iflytek.rpa.auth.sp.casdoor.filter;

import com.iflytek.rpa.auth.sp.casdoor.utils.ResponseUtils;
import java.io.IOException;
import java.util.Arrays;
import java.util.List;
import javax.servlet.*;
import javax.servlet.http.HttpServletRequest;
import javax.servlet.http.HttpServletResponse;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.core.annotation.Order;
import org.springframework.stereotype.Component;

/**
 * @desc: 认证过滤器，替代Spring Security的认证功能
 * @author: weilai <laiwei3@iflytek.com>
 * @create: 2025/12/11
 */
@Component
@Order(1)
@ConditionalOnProperty(name = "rpa.auth.deployment-mode", havingValue = "casdoor", matchIfMissing = true)
public class AuthenticationFilter implements Filter {

    private static final Logger logger = LoggerFactory.getLogger(AuthenticationFilter.class);

    /**
     * 公开端点列表（不需要认证的路径）
     */
    private static final List<String> PUBLIC_PATHS = Arrays.asList(
            "/api/rpa-auth/pre-authenticate",
            "/api/rpa-auth/tenant/list",
            "/api/rpa-auth/login",
            "/api/rpa-auth/verification-code/send",
            "/api/rpa-auth/register",
            "/api/rpa-auth/password/set",
            "/api/rpa-auth/logout",
            "/api/rpa-auth/login-status",
            "/api/rpa-auth/refresh-token",
            "/api/rpa-auth/user/history");

    @Override
    public void doFilter(ServletRequest request, ServletResponse response, FilterChain chain)
            throws IOException, ServletException {

        HttpServletRequest httpRequest = (HttpServletRequest) request;
        HttpServletResponse httpResponse = (HttpServletResponse) response;

        String requestURI = httpRequest.getRequestURI();

        // 检查是否是公开路径
        if (isPublicPath(requestURI)) {
            chain.doFilter(request, response);
            return;
        }

        // 检查用户是否已登录
        javax.servlet.http.HttpSession session = httpRequest.getSession(false);
        if (session == null) {
            logger.debug("未登录用户尝试访问受保护资源: {}", requestURI);
            ResponseUtils.fail(httpResponse, "unauthorized");
            return;
        }

        org.casbin.casdoor.entity.User user = (org.casbin.casdoor.entity.User) session.getAttribute("user");
        if (user == null) {
            logger.debug("session中无用户信息，拒绝访问: {}", requestURI);
            ResponseUtils.fail(httpResponse, "unauthorized");
            return;
        }

        // 用户已登录，继续处理请求
        chain.doFilter(request, response);
    }

    /**
     * 检查请求路径是否是公开路径
     *
     * @param requestURI 请求URI
     * @return 如果是公开路径返回true，否则返回false
     */
    private boolean isPublicPath(String requestURI) {
        if (requestURI == null || requestURI.isEmpty()) {
            return false;
        }

        // 移除查询参数
        String rawPath = requestURI.split("\\?")[0];

        // URL 解码，处理 %2e%2e、%2f 等编码穿越
        String decodedPath;
        try {
            decodedPath = java.net.URLDecoder.decode(rawPath, "UTF-8");
        } catch (Exception e) {
            logger.warn("URL解码失败，拒绝请求: {}", rawPath, e);
            return false;
        }

        // 归一化路径，解析掉 . 与 .. 等穿越序列
        // 例如 /api/rpa-auth/login/../dept/current 会被归一化为 /api/rpa-auth/dept/current
        String path = org.springframework.util.StringUtils.cleanPath(decodedPath);

        // 归一化后仍残留 ..（如越过根路径）或包含反斜杠、分号等可疑字符，视为非法路径，一律不放行
        if (path.contains("../") || path.contains("..\\") || path.contains(";")) {
            return false;
        }

        // 检查是否匹配公开路径
        for (String publicPath : PUBLIC_PATHS) {
            if (path.equals(publicPath) || path.startsWith(publicPath + "/")) {
                return true;
            }
        }

        return false;
    }
}
