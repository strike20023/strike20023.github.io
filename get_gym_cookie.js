/*
Script: get_gym_cookie.js
Description: Captures request headers for gym check.
*/

const targetUrl = "https://byty.bupt.edu.cn/bdlp_h5_fitness_test/public/index.php/index/Stadium/getInterval";

if ($request.url.indexOf("getInterval") !== -1) {
    const headers = $request.headers;
    const cookie = headers['Cookie'] || headers['cookie'];
    
    if (cookie) {
        const savedHeaders = {
            'Cookie': cookie,
            'User-Agent': headers['User-Agent'] || headers['user-agent'],
            'Referer': headers['Referer'] || headers['referer'],
            'Origin': headers['Origin'] || headers['origin'],
            'Host': headers['Host'] || headers['host']
        };
        
        const success = $persistentStore.write(JSON.stringify(savedHeaders), "gym_headers");
        
        if (success) {
            $notification.post("Gym Check", "Cookie Updated", "Successfully captured and saved new session headers.");
            console.log("Gym Check: Headers saved: " + JSON.stringify(savedHeaders));
        } else {
            $notification.post("Gym Check", "Error", "Failed to save headers.");
            console.log("Gym Check: Failed to save headers.");
        }
    } else {
        console.log("Gym Check: No cookie found in request headers.");
    }
}

$done({});
