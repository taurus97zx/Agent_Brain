``
###  StatefulSet
#### **创建 3 个 Nginx，给它们编好号（0,1,2），并且允许直接通过名字找到具体的某一个，而不是随机访问。**
```
# 1. 定义 Headless Service
apiVersion: v1
kind: Service
metadata:
  name: nginx-svc      # 【关键】服务名称，将作为 DNS 域名的一部分
  labels:
    app: nginx
spec:
  ports:
  - port: 80
    name: web
  clusterIP: None      # 【关键】必须设置为 None，这就是 "Headless" 的由来
  selector:
    app: nginx
---
# 2. 定义 StatefulSet
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: web            # 【关键】StatefulSet 名称，将作为 Pod 名字的前缀
spec:
  serviceName: "nginx-svc" # 【关键】必须指向上面创建的 Headless Service 名称
  replicas: 3
  selector:
    matchLabels:
      app: nginx
  template:
    metadata:
      labels:
        app: nginx
    spec:
      containers:
      - name: nginx
        image: nginx:1.21
        ports:
        - containerPort: 80
          name: web
```

**用户只能访问 nginx-svc，K8s 会做一个负载均衡，把你的请求随机扔给 web-0、web-1 或 web-2。**


#### **Pod 可以死，但它绑定的“硬盘”（PVC）永远属于它，数据不会丢，也不会乱**


```
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: web
spec:
  serviceName: "nginx"
  replicas: 2
  selector:
    matchLabels:
      app: nginx
  template:
    metadata:
      labels:
        app: nginx
    spec:
      containers:
      - name: nginx
        image: nginx
        ports:
        - containerPort: 80
          name: web
        volumeMounts:
        - name: www
          mountPath: /usr/share/nginx/html # 挂载点
  # 【核心配置：动态申请存储】
  volumeClaimTemplates:
  - metadata:
      name: www
    spec:
      accessModes: [ "ReadWriteOnce" ]
      storageClassName: "standard" # 假设集群有这个默认存储类
      resources:
        requests:
          storage: 1Gi
```

**差异化的数据，但是删除后。pod挂载的数据不会被删除。**
```
kubectl exec web-1 -- sh -c 'echo "我是 web-1 的独家数据" > /usr/share/nginx/html/index.html'
```

```
kubectl exec web-1 -- sh -c 'echo "我是 web-1 的独家数据" > /usr/share/nginx/html/index.html'
```