FROM ubuntu:22.04

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential cmake binutils ca-certificates socat \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/bfc
COPY . .
RUN cmake -S . -B build -DCMAKE_BUILD_TYPE=Debug \
    && cmake --build build -j2 \
    && test "$(getconf GNU_LIBC_VERSION)" = "glibc 2.35" \
    && chmod 755 /opt/bfc/run-session.sh \
    && useradd --create-home student

USER student
EXPOSE 1337
ENTRYPOINT ["socat", "TCP-LISTEN:1337,reuseaddr,fork", "EXEC:/opt/bfc/run-session.sh,stderr"]
