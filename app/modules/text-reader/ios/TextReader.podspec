Pod::Spec.new do |s|
  s.name           = 'TextReader'
  s.version        = '1.0.0'
  s.summary        = 'On-device text recognition (Apple Vision) for reading expiry dates'
  s.author         = ''
  s.homepage       = 'https://github.com/muktharamesh20/hackachusetts'
  s.platforms      = { :ios => '15.1' }
  s.source         = { git: '' }
  s.static_framework = true
  s.dependency 'ExpoModulesCore'
  s.source_files = '**/*.{h,m,swift}'
end
