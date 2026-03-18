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
            $notification.post("北邮健身房", "小饼干更新成功", "已成功抓取并保存新的请求头");
        } else {
            $notification.post("北邮健身房", "保存失败", "无法保存请求头信息");
        }
    } else {
        $notification.post("北邮健身房", "获取失败", "在请求头中未找到小饼干");
    }
}

$done({});
