FROM nodered/node-red:4.0.9
COPY package.json /data/package.json
RUN cd /data && npm install --omit=dev --no-audit --no-fund
COPY settings.js flows.json /data/
ENV NODE_RED_USER_DIR=/data
HEALTHCHECK --interval=20s --timeout=5s --start-period=30s --retries=5 \
    CMD node -e "require('http').get('http://127.0.0.1:1880/', (res) => process.exit(res.statusCode === 200 ? 0 : 1)).on('error', () => process.exit(1))"
