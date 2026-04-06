const { execSync } = require('child_process');
console.log(execSync('git log -p -n 5 proxy_farm.py').toString().substring(0, 8000));
