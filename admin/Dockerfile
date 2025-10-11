FROM nginx:alpine

# 复制管理后台页面
COPY index.html /usr/share/nginx/html/

# 暴露端口
EXPOSE 80

# 启动nginx
CMD ["nginx", "-g", "daemon off;"]