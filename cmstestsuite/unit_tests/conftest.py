# This file is meant to be used for creating pytest fixtures.
# It's a bit of a hack, but we can put global initialization here.

# Make bcrypt run faster in tests. Default difficulty is 12,
# which takes around 250ms per hash. This one takes <1ms.
import cmscommon.crypto
cmscommon.crypto.BCRYPT_ROUNDS = 4
