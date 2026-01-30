
### 一般情况下都会同时写出流式和非流式的方法
    @abstractmethod
    def _generate_node(self, state):
        """生成回答节点逻辑，子类必须实现"""
        pass

    async def _generate_node_stream(self, state):
        """
        生成回答节点逻辑的流式版本
        
        参数:
            state: 当前状态
            
        返回:
            AsyncGenerator[str, None]: 流式响应生成器
        """
        # 默认实现 - 应由子类覆盖
        result = self._generate_node(state)
        if "messages" in result and result["messages"]:
            message = result["messages"][0]
            content = message.content if hasattr(message, "content") else str(message)
            
            # 模拟流式输出
            for i in range(0, len(content), self.chunk_size):
                yield content[i:i+self.chunk_size]
                await asyncio.sleep(0.01)


    async def _generate_node_async(self, state):
        """
        生成回答节点逻辑的异步版本
        
        参数:
            state: 当前状态
            
        返回:
            Dict: 包含消息的结果字典
        """
        # 这个默认实现只是调用同步版本
        # 子类应该提供真正的异步实现
        def sync_generate():
            return self._generate_node(state)
            
        # 在线程池中运行同步代码，避免阻塞事件循环
        return await asyncio.get_event_loop().run_in_executor(None, sync_generate)


    langgraph的调用方法
    workflow.add_node("generate", self._generate_node)


    # 添加从开始到Agent的边，这段代码表示的意思是agent有两个情况可以连接，retrieve时和end时。
    workflow.add_edge(START, "agent")
    workflow.add_conditional_edges(
        "agent",
        tools_condition,
        {
            "tools": "retrieve",
            END: END,
        },
    )
