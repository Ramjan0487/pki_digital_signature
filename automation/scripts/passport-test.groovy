import static com.kms.katalon.core.webui.keyword.WebUiBuiltInKeywords as WebUI

WebUI.openBrowser('')
WebUI.navigateToUrl('https://secure-login.com')

WebUI.uploadFile(findTestObject('Upload_Button'), 'passport.jpg')
WebUI.click(findTestObject('Submit_Button'))

String result = WebUI.getText(findTestObject('Result'))

WebUI.comment(result)
