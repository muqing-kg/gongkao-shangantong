# 同舟共济 · 学习平台
# 镜像里装的是「应用 + 题库 + 图片」，密码与学习数据都不进镜像。
FROM node:20-alpine

LABEL org.opencontainers.image.title="同舟共济" \
      org.opencontainers.image.description="公务员考试学习与成长平台" \
      org.opencontainers.image.source="https://github.com/muqing-kg/gongkao-shangantong"

WORKDIR /app

# 只拷贝运行必需的东西（见 .dockerignore）
COPY . .

ENV NODE_ENV=production \
    PORT=8848 \
    DATA_DIR=/app/server/data

# 学习数据、密码哈希都落在这里，挂卷持久化
VOLUME ["/app/server/data"]

EXPOSE 8848

HEALTHCHECK --interval=60s --timeout=5s --start-period=10s --retries=3 \
  CMD wget -q --spider http://127.0.0.1:8848/login.html || exit 1

CMD ["node", "server/index.js"]
