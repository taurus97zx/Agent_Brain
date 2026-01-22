### 核心网主要网元架构
![alt text](image.png)

#### 网元流程
![alt text](Snipaste_2026-01-22_14-25-07.png)




### 核心网K8s网络配置
#### **Pod 资源请求与限制**
**核心网/边缘计算:** 5G UPF、AMF、SMF 等网元对 CPU 和内存有严格要求。**请求 (Requests)** 确保 Pod 获得足够的资源，**限制 (Limits)** 防止单个 Pod 耗尽节点资源。

```
resources:
  requests:
    cpu: "1000m" # 1 core
    memory: "2Gi"
  limits:
    cpu: "2000m" # 2 cores
    memory: "4Gi"
```

 **核心网/边缘计算:** 保证高可用和性能。
 - **Pod Affinity:** 强制让互为依赖的网元（如 SMF-UPF）尽可能部署在**同一节点**或**同一可用区**，降低时延。
- **Pod Anti-Affinity:** 确保关键网元（如两个 AMF 实例）**不在同一节点**，防止单点故障。

```
affinity:
  podAffinity:
    requiredDuringSchedulingIgnoredDuringExecution:
      labelSelector:
        matchExpressions:
          - key: app
            operator: In
            values:
              - smf
      topologyKey: "kubernetes.io/hostname" # 强制同节点
  podAntiAffinity:
    preferredDuringSchedulingIgnoredDuringExecution:
      - weight: 100
        podAffinityTerm:
          labelSelector:
            matchExpressions:
              - key: app
                operator: In
                values:
                  - amf
          topologyKey: "kubernetes.io/hostname" # 尽量不同节点
```


**解释：当前 Pod 必须被调度到“已经运行了 `app=smf` Pod 的节点上， 调度器会尽量把当前 Pod 调度到“没有 `amf` Pod 的节点上”，  但如果实在没有这样的节点，也会妥协。



#### 网络配置
5G 的 UPF（用户面功能）是一个“流量怪兽”。它需要：
1. **N3 接口**：对接基站（GTP-U 流量）。
2. **N4 接口**：对接 SMF（控制信令）。
3. **N6 接口**：对接外部数据网络（Internet/MEC）。
4. **极低时延**：不能忍受内核协议栈的多次拷贝。

```
apiVersion: "cilium.io/v2"
kind: CiliumNetworkPolicy
metadata:
  name: allow-amf-to-smf-n11
spec:
  endpointSelector:
    matchLabels:
      app: smf
  ingress:
  - fromEndpoints:
    - matchLabels:
        app: amf
    toPorts:
    - ports:
      - port: "8080"
        protocol: TCP
      rules:
        http:
        - method: "POST"
          path: "/nsmf-pdusess/v1/pdu-sessions" # 仅允许创建会话的 API
```