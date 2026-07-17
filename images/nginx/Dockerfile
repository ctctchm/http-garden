FROM http-garden-soil:latest

RUN apt -y update && apt -y upgrade && \
    apt -y install git libpcre2-dev zlib1g-dev libssl-dev libxml2-dev libxslt-dev && \
    git clone https://github.com/nginx/nginx.git /app/nginx && \
    git clone https://github.com/nginx/njs.git /app/njs

ARG APP_VERSION

# 1. Compiler njs avec clang standard (sans AFL/ASAN)
RUN cd /app/njs && \
    CC=clang CFLAGS="" ./configure --no-openssl --no-libxml2 --no-zlib --no-pcre --no-quickjs && \
    make libnjs

# 2. Compiler Nginx avec AFL + ASAN
RUN cd /app/nginx && \
    git checkout $APP_VERSION && \
    ./auto/configure \
        --with-cc="$(which clang)" \
        --add-dynamic-module=/app/njs/nginx && \
    AFL_USE_ASAN=1 make -j$(nproc) CC="afl-clang-fast" && \
    make install

COPY ./index.js /app

ARG CONFIG_FILE
COPY $CONFIG_FILE /usr/local/nginx/conf/nginx.conf

ARG BACKEND
RUN sed -i "s/PROXY_BACKEND_PLACEHOLDER/$BACKEND/g" /usr/local/nginx/conf/nginx.conf

RUN groupadd nobody || true

CMD export AFL_MAP_SIZE="$(AFL_DEBUG=1 afl-showmap -o /dev/null -t 2147483647 -- /usr/local/nginx/sbin/nginx 2>&1 | grep -oP '__afl_final_loc \d+' | tail -n 1 | awk '{print $2}')" \
           AFL_PRELOAD="/usr/local/nginx/$(cat /usr/local/nginx/conf/nginx.conf | grep -oP 'load_module [^;]*' | awk '{print $2}')" \
           ASAN_OPTIONS=detect_odr_violation=0 \
 && exec afl-showmap -o /tmp/trace -t 2147483647 -- /usr/local/nginx/sbin/nginx