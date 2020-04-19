<?php

function characet($data) {
  if( !empty($data) ) {
    $fileType = mb_detect_encoding($data , array('UTF-8','GBK','LATIN1','BIG5'));
    if( $fileType != 'UTF-8') {
      $data = mb_convert_encoding($data ,'utf-8' , $fileType);
    }
  }
  return $data;
}

header("Content-Type: text/plain; charset=utf-8");

if(!isset($_GET['url'])) {
	die('缺少参数url');
}
$url_reg = '%^(?:(?:https?|ftp)://)(?:\S+(?::\S*)?@|\d{1,3}(?:\.\d{1,3}){3}|(?:(?:[a-z\d\x{00a1}-\x{ffff}]+-?)*[a-z\d\x{00a1}-\x{ffff}]+)(?:\.(?:[a-z\d\x{00a1}-\x{ffff}]+-?)*[a-z\d\x{00a1}-\x{ffff}]+)*(?:\.[a-z\x{00a1}-\x{ffff}]{2,6}))(?::\d+)?(?:[^\s]*)?$%iu';
if(!preg_match($url_reg, $_GET['url'])) {
	die('url:无效的URL');
}

$url = $_GET['url'];

$curl = curl_init();

curl_setopt_array($curl, array(
  CURLOPT_URL => $url,
  CURLOPT_RETURNTRANSFER => true,
  CURLOPT_FOLLOWLOCATION => 1,
  CURLOPT_ENCODING => "",
  CURLOPT_MAXREDIRS => 10,
  CURLOPT_TIMEOUT => 30,
  CURLOPT_HTTP_VERSION => CURL_HTTP_VERSION_1_1,
  CURLOPT_CUSTOMREQUEST => "GET",
));

$response = curl_exec($curl);
$err = curl_error($curl);

curl_close($curl);

if ($err) {
  echo $err;
} else {
  echo characet($response);
}
