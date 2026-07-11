// gee_terraclimate.js — TerraClimate 7월 토양수분+VPD를 미국 카운티별로 export
// 실행: https://code.earthengine.google.com 에 붙여넣고 Run → Tasks 탭에서 Run → Google Drive에 CSV 저장
// (Google Earth Engine 무료 계정 필요: earthengine.google.com 에서 가입)
//
// 결과 CSV 컬럼: GEOID(=5자리 FIPS), year, soil(7월 토양수분), vpd(7월 VPD)
// 참고: 트리 모델은 스케일 불변이라 TerraClimate의 원단위/스케일팩터는 신경 안 써도 됨.

var counties = ee.FeatureCollection('TIGER/2018/Counties');   // 미국 카운티 경계(FIPS=GEOID)
var tc = ee.ImageCollection('IDAHO_EPSCOR/TERRACLIMATE');
var years = ee.List.sequence(1981, 2015);

var rows = ee.FeatureCollection(years.map(function (y) {
  y = ee.Number(y);
  var img = tc
    .filter(ee.Filter.calendarRange(y, y, 'year'))
    .filter(ee.Filter.calendarRange(7, 7, 'month'))   // 7월 (개화기)
    .first()
    .select(['soil', 'vpd']);                          // 토양수분, 증기압차
  var stats = img.reduceRegions({
    collection: counties,
    reducer: ee.Reducer.mean(),
    scale: 4000
  });
  return stats.map(function (f) { return f.set('year', y); });
}).flatten());

Export.table.toDrive({
  collection: rows,
  description: 'terraclimate_july_county',
  fileFormat: 'CSV',
  selectors: ['GEOID', 'year', 'soil', 'vpd']          // 필요한 컬럼만
});
