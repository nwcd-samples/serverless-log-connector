# serverless-log-connector

## 架构图
![架构图](/assets/rdslog.drawio.png)

## 部署方法
### 手动部署

#### 配置任务
1. 进入glue服务，创建一个 glue python script job
![glue job](/assets/glue_job1.png)
2. 将connectors文件夹下的mysql.py 的python code  复制脚本编辑器。注意修改注释部分
![glue job](/assets/gcode.png)
3. 配置 glue job相关的参数，如执行role, 重试次数改为 0，超时时间根据要同步的数据量估计，1GB的数据大概要3分钟
![glue job](/assets/glueconfig.png)

4. 配置执行角色，角色策略参考下图及代码
![glue role](/assets/rolerule.png)
```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "VisualEditor0",
            "Effect": "Allow",
            "Action": [
                "s3:PutObject",
                "dynamodb:PutItem",
                "rds:DownloadDBLogFilePortion",
                "dynamodb:GetItem",
                "rds:DownloadCompleteDBLogFile",
                "rds:DescribeDBLogFiles",
                "s3:PutObjectTagging"
            ],
            "Resource": [
                "arn:aws-cn:rds:cn-northwest-1:xxxxxxx:db:*",
                "arn:aws-cn:dynamodb:cn-northwest-1:xxxxxx:table/db_log_to_s3",
                "arn:aws-cn:s3:::tx-audit-log2/*"
            ]
        }
    ]
}
```
注意修改上面的账号信息，dynamodb 表信息，s3 桶信息
4. 在 glue schedules页面配置执行计划 （第一次同步，由于数据量较大，建议手动触发， 等第一次同步成功以后，后续的增量同步，可以使用scheduler触发执行）
![glue job](/assets/glueschedule.png)
5. 配置dynamodb, 如图新建一个dynamodb table, 并按截图配置
![dynamodb](/assets/dynamodb1.png)

#### 配置监控
1. 进入sns控制台 创建 sns topic
2. 在sns 控制台，右边导航栏创建订阅,配置相关的收件人信息
3. 在cloudwatch 创建rule, event patten 如下，将 rds_to_s3 替换成你的glue job name
![cloudwatchrule](/assets/cloudwatchrule.png)

要把 rds_to_s3 改成你的glue job的名称
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
4. 配置cloudwatch rule 目标。选择前面创建的主题作为规则目标
![cloudwatchrule](/assets/ctarget.png)

## 注意
第一次跑，要评估一下目前审计日志的大小，如果使用glue 跑，超时时间大一些，或者不同的job跑不同的db


