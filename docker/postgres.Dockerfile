FROM postgres:16-alpine

# Alpine's minimal PostgreSQL image does not include the `locale` utility
# or locale data by default. Installing these packages prevents the
# "sh: locale: not found" / "no usable system locales were found" warning
# during a fresh cluster initialization.
RUN apk add --no-cache \
        musl-locales \
        musl-locales-lang

ENV LANG=en_US.UTF-8 \
    LC_ALL=en_US.UTF-8
