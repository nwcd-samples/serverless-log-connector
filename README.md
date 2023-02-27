# serverless-log-connector

## 架构图
![架构图](/assets/rdslog.drawio.png)

## 部署方法
### 手动部署

#### 配置任务
1. 创建一个 glue python script job
2. 将对应的 connector 的python code  复制进去
3. 配置 glue job相关的参数，如执行role, 重试次数改为 0，超时时间根据要同步的数据量估计，1GB的数据大概要3分钟
4. 在 glue schedules页面配置执行计划 （第一次同步，由于数据量较大，建议手动触发， 等第一次同步成功以后，后续的增量同步，可以使用scheduler触发执行）

#### 配置监控
1. 进入sns控制台 创建 sns topic
2. 在sns 控制台，右边导航栏创建订阅
3. 在cloudwatch 创建rule, event patten 如下，将 rds_to_s3 替换成你的glue job name
```
{
  "source": ["aws.glue"],
  "detail-type": ["Glue Job State Change"],
  "detail": {
    "jobName": ["rds_to_s3"],
    "state": ["FAILED"]
  }
}
```


