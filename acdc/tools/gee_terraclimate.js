// gee_terraclimate.js — TerraClimate 7월 토양수분+VPD를 미국 카운티별로 export
// 실행: https://code.earthengine.google.com 에 붙여넣고 Run → Tasks 탭에서 Run → Google Drive에 CSV 저장
// (Google Earth Engine 무료 계정 필요: earthengine.google.com 에서 가입)
//
// 결과 CSV 컬럼: GEOID(=5자리 FIPS), year, soil(7월 토양수분), vpd(7월 VPD)
// 참고: 트리 모델은 스케일 불변이라 TerraClimate의 원단위/스케일팩터는 신경 안 써도 됨.

// 우리 프로젝트가 쓰는 12개 주만 계산 → 전체(3,100개)의 1/3로 줄어 ~3배 빠름
// (IA IL IN KS MN MO ND NE OH SD TX WI). 전체가 필요하면 .filter(...) 줄을 지우면 됨.
var STATES = ['19', '17', '18', '20', '27', '29', '38', '31', '39', '46', '48', '55'];
var counties = ee.FeatureCollection('TIGER/2018/Counties')
  .filter(ee.Filter.inList('STATEFP', STATES));
var tc = ee.ImageCollection('IDAHO_EPSCOR/TERRACLIMATE');
var years = ee.List.sequence(1981, 2015);

var rows = ee.FeatureCollection(years.map(function (y) {
  y = ee.Number(y);
  var img = tc
    .filter(ee.Filter.calendarRange(y, y, 'year'))
    .filter(ee.Filter.calendarRange(7, 7, 'month'))   // 7월 (개화기)
    .first()
    .select(['soil', 'vpd', 'pr', 'tmmx']);            // 토양수분, 증기압차, 7월강수, 7월최고기온
  var stats = img.reduceRegions({
    collection: counties,
    reducer: ee.Reducer.mean(),
    scale: 4000
  });
  return stats.map(function (f) { return f.set('year', y); });
})).flatten();   // flatten 은 List 가 아니라 FeatureCollection 메서드로 (연도별 FC들을 하나로 병합)

Export.table.toDrive({
  collection: rows,
  description: 'terraclimate_july_county',
  fileFormat: 'CSV',
  selectors: ['GEOID', 'year', 'soil', 'vpd', 'pr', 'tmmx']   // 필요한 컬럼만
});
