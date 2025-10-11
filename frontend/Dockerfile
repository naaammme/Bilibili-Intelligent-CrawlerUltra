FROM node:20-alpine AS builder

WORKDIR /app

# 直接复制所有文件（包括 node_modules）
COPY . .

# 如果 node_modules 不存在或不完整，才安装
RUN if [ ! -d "node_modules" ]; then npm install; fi

# 构建生产版本
RUN npm run build

# 生产阶段 - 使用 Nginx
FROM nginx:alpine

# 复制构建产物到 Nginx
COPY --from=builder /app/dist /usr/share/nginx/html


# 暴露端口
EXPOSE 80

# 启动nginx
CMD ["nginx", "-g", "daemon off;"]