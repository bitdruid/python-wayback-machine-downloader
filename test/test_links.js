// Example JavaScript File: example.js

// External script with absolute URL
var externalScript = document.createElement('script');
externalScript.src = 'http://example.com/js/external-script.js';
document.head.appendChild(externalScript);

// External script with relative URL
var localScript = document.createElement('script');
localScript.src = '/js/local-script.js';
document.head.appendChild(localScript);

// Inline style with absolute URL in background image
var element = document.createElement('div');
element.style.backgroundImage = "url('http://example.com/images/bg.png')";
document.body.appendChild(element);

// Inline style with relative URL in background image
element.style.backgroundImage = "url('/images/bg.png')";

// CSS in JavaScript with absolute URL
var css = "body { background-image: url('http://example.com/images/body-bg.png'); }";
var style = document.createElement('style');
style.type = 'text/css';
style.appendChild(document.createTextNode(css));
document.head.appendChild(style);

// CSS in JavaScript with relative URL
var cssLocal = "body { background-image: url('/images/body-bg.png'); }";
var styleLocal = document.createElement('style');
styleLocal.type = 'text/css';
styleLocal.appendChild(document.createTextNode(cssLocal));
document.head.appendChild(styleLocal);

// Image element with absolute URL
var imgElement = document.createElement('img');
imgElement.src = 'http://example.com/images/logo.png';
document.body.appendChild(imgElement);

// Image element with relative URL
var imgLocalElement = document.createElement('img');
imgLocalElement.src = '/images/logo.png';
document.body.appendChild(imgLocalElement);

// Fetch API call with absolute URL
fetch('http://example.com/api/data')
    .then(response => response.json())
    .then(data => console.log(data));

// Fetch API call with relative URL
fetch('/api/data')
    .then(response => response.json())
    .then(data => console.log(data));

// XMLHttpRequest with absolute URL
var xhr = new XMLHttpRequest();
xhr.open('GET', 'http://example.com/api/data', true);
xhr.send();

// XMLHttpRequest with relative URL
var xhrLocal = new XMLHttpRequest();
xhrLocal.open('GET', '/api/data', true);
xhrLocal.send();
