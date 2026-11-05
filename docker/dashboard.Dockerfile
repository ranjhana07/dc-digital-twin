FROM nginx:1.27-alpine
COPY dashboard/nginx.conf /etc/nginx/conf.d/default.conf
COPY dashboard/index.html /usr/share/nginx/html/index.html
COPY dashboard/css /usr/share/nginx/html/css
COPY dashboard/js /usr/share/nginx/html/js
HEALTHCHECK --interval=15s --timeout=3s --retries=3 \
    CMD wget -q -O /dev/null http://127.0.0.1/ || exit 1
