Subject: Cut your CI/CD pipeline time by 50%

Hi Sarah,

I'm the founder of Velocity AI, and we help engineering teams run their test suites faster using ML-based test selection.

Our system analyzes your commit history and test results to predict which tests are most likely to fail, so you only run the ones that matter. Teams using our approach typically see 40-60% reduction in pipeline times.

We recently helped a Series B startup cut their deploy pipeline from 45 minutes to 18 minutes, which let them ship 3x more frequently.

A quick look at your public repo suggests ~40% of your 2,000+ Cypress integration tests re-test unchanged code paths on each push — that's usually the single biggest bottleneck in pipelines like yours.

I put together a 1-page analysis showing which of those tests would be safe to skip per-push — want me to send it over?

Best,
Alex Chen
Founder, Velocity AI
