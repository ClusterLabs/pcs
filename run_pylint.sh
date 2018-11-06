#!/bin/bash
cd $(dirname $0)
RC=0
for file_name in $(find ./pcs -name '*.py'); do
        echo "Checking file: ${file_name}"
        pylint --rcfile pylintrc --persistent=n --reports=n --score=n  ${file_name}
        RC=$(($RC | $?))
done
exit $RC
