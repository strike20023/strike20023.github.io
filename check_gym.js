/*
Script: check_gym.js
Description: Checks gym availability using stored headers.
*/

const targetUrl = "https://byty.bupt.edu.cn/bdlp_h5_fitness_test/public/index.php/index/Stadium/getInterval";
const requestBody = "venue_id=1&stadium_id=2&user_range=%5B1%5D&category_id=8";

function checkGym() {
    const savedData = $persistentStore.read("gym_headers");
    
    if (!savedData) {
        $notification.post("Gym Check", "Error", "No saved headers found. Please visit the gym page to capture headers.");
        console.log("Gym Check: No saved headers found.");
        $done();
        return;
    }

    let headers;
    try {
        headers = JSON.parse(savedData);
    } catch (e) {
        $notification.post("Gym Check", "Error", "Failed to parse saved headers.");
        console.log("Gym Check: Failed to parse saved headers: " + e.message);
        $done();
        return;
    }

    // Ensure Content-Type is set for POST request
    headers['Content-Type'] = 'application/x-www-form-urlencoded; charset=UTF-8';

    const request = {
        url: targetUrl,
        headers: headers,
        body: requestBody
    };

    $httpClient.post(request, function(error, response, data) {
        if (error) {
            $notification.post("Gym Check", "Network Error", error);
            console.log("Gym Check: Network Error: " + error);
            $done();
            return;
        }

        try {
            const result = JSON.parse(data);
            
            if (result.status === 0 && result.info === "登录信息失效,请退出重新登录") {
                $notification.post("Gym Check", "Session Expired", "Please visit the gym page again to update your session.");
                console.log("Gym Check: Session expired.");
            } else if (result.status === 1 && result.info === "查询成功") {
                // You can add more detailed checks here, e.g., checking available slots in result.data.interval
                $notification.post("Gym Check", "Success", "Gym status checked successfully.");
                console.log("Gym Check: Request successful.");
            } else {
                $notification.post("Gym Check", "Unknown Response", "Received unexpected response: " + result.info);
                console.log("Gym Check: Unexpected response: " + JSON.stringify(result));
            }
        } catch (e) {
            $notification.post("Gym Check", "Parse Error", "Failed to parse response data.");
            console.log("Gym Check: Failed to parse response data: " + e.message);
            console.log("Gym Check: Raw response: " + data);
        }
        
        $done();
    });
}

checkGym();
