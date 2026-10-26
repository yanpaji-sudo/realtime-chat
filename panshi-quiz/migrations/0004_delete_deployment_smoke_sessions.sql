-- Remove only dummy test sessions created by the deployment smoke check.
-- This does not affect real participant scores or certificates.
DELETE FROM attempts WHERE nickname='部署接口检测' AND finished_at IS NULL;
