Subject: 700 of your Cypress tests might be redundant on every push

Hi Sarah,

Your public repo runs 2,000+ Cypress integration tests on every push — I ran an analysis and found ~700 of them have zero correlation with recent code changes. That's likely your single biggest pipeline bottleneck.

I'm Alex Chen, founder of Velocity AI. We use ML-based test selection to predict which tests are most likely to fail per-commit, so teams only run the ones that matter. We recently helped a Series B startup cut their deploy pipeline from 45 minutes to 18 minutes, which let them ship 3x more frequently.

I put together a 1-page analysis showing which of your 2,000+ Cypress tests would be safe to skip per-push — want me to send it over?

Best,
Alex Chen
Founder, Velocity AI
