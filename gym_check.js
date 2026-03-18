/*
Script: check_gym.js
Description: Checks gym availability using stored headers.
*/

const targetUrl = "https://byty.bupt.edu.cn/bdlp_h5_fitness_test/public/index.php/index/Stadium/getInterval";
const requestBody = "venue_id=1&stadium_id=2&user_range=%5B1%5D&category_id=8";

function checkGym() {
    const savedData = $persistentStore.read("gym_headers");
    
    if (!savedData) {
        $notification.post("北邮健身房", "配置缺失", "未找到保存的请求头，请先访问健身房页面");
        $done();
        return;
    }

    let headers;
    try {
        headers = JSON.parse(savedData);
    } catch (e) {
        $notification.post("北邮健身房", "解析失败", "无法读取保存的请求头信息");
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
            $notification.post("北邮健身房", "网络错误", "请求失败，请检查网络连接");
            $done();
            return;
        }

        try {
            const result = JSON.parse(data);
            
            if (result.status === 0 && result.info === "登录信息失效,请退出重新登录") {
                $notification.post("北邮健身房", "登录失效", "请重新访问健身房页面更新登录状态");
            } else if (result.status === 1 && result.info === "查询成功") {
                let availableSlots = [];
                if (result.data && result.data.interval && result.data.interval.length > 0) {
                    result.data.interval.forEach(day => {
                        if (day.list && day.list.length > 0) {
                            day.list.forEach(slotArray => {
                                slotArray.forEach(slot => {
                                    if (slot.is_lock == 1 && slot.is_open == 1 && slot.max > slot.selected) {
                                        availableSlots.push(`日期：${slot.date.slice(5)} 时间：${slot.interval_time} 剩余：${slot.max - slot.selected}`);
                                    }
                                });
                            });
                        }
                    });
                }

                if (availableSlots.length > 0) {
                    let msg = availableSlots.slice(0, 5).join('\n');
                    if (availableSlots.length > 5) {
                        msg += `\n...等共 ${availableSlots.length} 个时段`;
                    }
                    $notification.post("🏋️ 健身房有空位！", "发现可预约时段", msg);
                }
            } else {
                $notification.post("北邮健身房", "小饼干失效", JSON.stringify(result));
            }
        } catch (e) {
            $notification.post("北邮健身房", "数据错误", "服务器返回的数据格式不正确");
        }
        
        $done();
    });
}

checkGym();
