# 使用 Red Hat 官方的 OpenJDK 8 基础镜像
FROM registry.access.redhat.com/ubi8/openjdk-8

# 设置 WildFly 版本
ENV WILDFLY_VERSION 23.0.2.Final
ENV WILDFLY_SHA1 9e813e514715979b648a0a945b87f99a34b2f72f

# 下载并解压 WildFly
RUN curl -O https://github.com/wildfly/wildfly/releases/download/$WILDFLY_VERSION/wildfly-$WILDFLY_VERSION.tar.gz \
    && echo "$WILDFLY_SHA1  wildfly-$WILDFLY_VERSION.tar.gz" | sha1sum -c - \
    && tar xf wildfly-$WILDFLY_VERSION.tar.gz \
    && mv wildfly-$WILDFLY_VERSION /opt/wildfly \
    && rm wildfly-$WILDFLY_VERSION.tar.gz

# 为 WildFly 创建用户和组 (ubi8/openjdk-8 镜像可能没有预置 jboss 用户)
RUN groupadd -r jboss -g 1000 && useradd -u 1000 -r -g jboss -m -d /opt/wildfly -s /sbin/nologin jboss \
    && chown -R jboss:jboss /opt/wildfly

# 设置 WildFly 用户
USER jboss

# 设置工作目录
WORKDIR /opt/wildfly

# 复制配置文件和部署文件
COPY config/ /opt/wildfly/standalone/configuration/
COPY deployments/ /opt/wildfly/standalone/deployments/

# 替换 Windows 路径 (根据您的具体配置文件修改)
RUN sed -i 's|C:\\my\\app\\logs|/var/log/myapp|g' /opt/wildfly/standalone/configuration/standalone.xml

# 暴露端口
EXPOSE 8080 9990

# 设置启动命令
CMD ["/opt/wildfly/bin/standalone.sh", "-b", "0.0.0.0", "-bmanagement", "0.0.0.0"]
