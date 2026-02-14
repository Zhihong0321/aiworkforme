# UniAPI.io - Gemini API Documentation

## Overview
UniAPI.io provides a unified API interface for multiple AI providers, including Google's Gemini models. This documentation covers the Gemini API integration through UniAPI.io.

**Base URL**: `https://api.uniapi.io`

## Authentication

All Gemini API requests require authentication via a custom header:

```
x-goog-api-key: <your-api-key>
```

## Available Endpoints

### 1. Non-Streaming Chat (Synchronous)
**Endpoint**: `POST /gemini/v1beta/models/{mode}:generateContent`

- **Path Parameter**: `{mode}` - Replace with model name (e.g., `gemini-2.5-flash`)
- **Content-Type**: `application/json`
- **Response**: Complete response in one request

### 2. Streaming Chat (Asynchronous)
**Endpoint**: `POST /gemini/v1beta/models/{mode}:streamGenerateContent`

- **Path Parameter**: `{mode}` - Replace with model name
- **Content-Type**: `application/json`
- **Response**: Server-sent events stream

## Supported Models

- `gemini-2.5-flash` - Fast, efficient model
- `gemini-2.5-flash-preview-tts` - Text-to-speech model
- `gemini-2.5-flash-image` - Image generation model
- Other Gemini variants as available

## Request Structure

### Basic Request Body
```json
{
    "contents": [
        {
            "role": "user",
            "parts": [
                {
                    "text": "Your prompt here"
                }
            ]
        }
    ],
    "generationConfig": {
        "temperature": 0.7,
        "maxOutputTokens": 1024,
        "topP": 0.95,
        "topK": 40
    },
    "system_instruction": {
        "parts": {
            "text": "System prompt"
        }
    }
}
```

## Content Types Supported

### 1. Text Content
```json
{
    "text": "Your text prompt"
}
```

### 2. Image Content (Input)
```json
{
    "inline_data": {
        "mime_type": "image/jpeg",
        "data": "base64_encoded_image_data"
    }
}
```

Supported image formats:
- JPEG (`image/jpeg`)
- PNG (`image/png`)
- WEBP (`image/webp`)
- HEIC (`image/heic`)
- HEIF (`image/heif`)

### 3. Audio Content (Input/Output)
```json
{
    "inline_data": {
        "mime_type": "audio/wav",
        "data": "base64_encoded_audio_data"
    }
}
```

Supported audio formats:
- WAV (`audio/wav`)
- MP3 (`audio/mp3`)
- AIFF (`audio/aiff`)
- AAC (`audio/aac`)
- OGG (`audio/ogg`)
- FLAC (`audio/flac`)

### 4. Video Content (Input)
```json
{
    "inline_data": {
        "mime_type": "video/mp4",
        "data": "base64_encoded_video_data"
    }
}
```

Supported video formats:
- MP4 (`video/mp4`)
- MPEG (`video/mpeg`)
- MOV (`video/mov`)
- AVI (`video/avi`)
- WebM (`video/webm`)

## Generation Configuration Options

```json
{
    "generationConfig": {
        "temperature": 0.7,
        "maxOutputTokens": 2048,
        "topP": 0.95,
        "topK": 40,
        "stopSequences": ["END"],
        "responseMimeType": "application/json",
        "responseSchema": {},
        "responseModalities": ["TEXT", "IMAGE", "AUDIO"],
        "speechConfig": {}
    }
}
```

### Configuration Parameters

- **temperature** (number): Controls randomness (0.0-2.0)
- **maxOutputTokens** (integer): Maximum tokens to generate
- **topP** (number): Nucleus sampling parameter
- **topK** (integer): Top-k sampling parameter
- **stopSequences** (array): Stop generation at these sequences
- **responseMimeType** (string): Output format (e.g., `application/json`)
- **responseSchema** (object): JSON schema for structured output
- **responseModalities** (array): Output modalities (`["TEXT"]`, `["IMAGE"]`, `["AUDIO"]`)
- **speechConfig** (object): Text-to-speech configuration

## Text-to-Speech (TTS) Configuration

### Single Speaker
```json
{
    "generationConfig": {
        "responseModalities": ["AUDIO"],
        "speechConfig": {
            "voiceConfig": {
                "prebuiltVoiceConfig": {
                    "voiceName": "Kore"
                }
            }
        }
    }
}
```

### Multi-Speaker
```json
{
    "generationConfig": {
        "responseModalities": ["AUDIO"],
        "speechConfig": {
            "multiSpeakerVoiceConfig": {
                "speakerVoiceConfigs": [
                    {
                        "speaker": "Speaker1",
                        "voiceConfig": {
                            "prebuiltVoiceConfig": {
                                "voiceName": "Kore"
                            }
                        }
                    },
                    {
                        "speaker": "Speaker2",
                        "voiceConfig": {
                            "prebuiltVoiceConfig": {
                                "voiceName": "Puck"
                            }
                        }
                    }
                ]
            }
        }
    }
}
```

### Available Voices
- Kore
- Puck
- (And other Gemini TTS voices)

### Supported Languages
de-DE, en-AU, en-GB, en-IN, en-US, es-US, fr-FR, hi-IN, pt-BR, ar-XA, es-ES, fr-CA, id-ID, it-IT, ja-JP, tr-TR, vi-VN, bn-IN, gu-IN, kn-IN, ml-IN, mr-IN, ta-IN, te-IN, nl-NL, ko-KR, cmn-CN, pl-PL, ru-RU, th-TH

## Tools and Function Calling

### Tool Types

#### 1. Code Execution
```json
{
    "tools": [
        {
            "codeExecution": {}
        }
    ]
}
```

#### 2. Google Search (Grounding)
```json
{
    "tools": [
        {
            "googleSearch": {}
        }
    ]
}
```

#### 3. Custom Functions
```json
{
    "tools": [
        {
            "functionDeclarations": [
                {
                    "name": "get_weather",
                    "description": "Get current weather for a location",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "location": {
                                "type": "string",
                                "description": "City name"
                            }
                        },
                        "required": ["location"]
                    }
                }
            ]
        }
    ]
}
```

### Tool Configuration
```json
{
    "tool_config": {
        "function_calling_config": {
            "mode": "AUTO",
            "allowedFunctionNames": ["function1", "function2"]
        }
    }
}
```

**Modes**:
- `AUTO` - Model decides when to call functions
- `ANY` - Model must call a function
- `NONE` - Model should not call functions

## Structured Output

### JSON Output with Schema
```json
{
    "generationConfig": {
        "responseMimeType": "application/json",
        "responseSchema": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "value": {"type": "number"}
                },
                "required": ["name", "value"]
            }
        }
    }
}
```

## Conversation History (Multi-turn)

```json
{
    "contents": [
        {
            "role": "user",
            "parts": [{"text": "Hello!"}]
        },
        {
            "role": "model",
            "parts": [{"text": "Hi! How can I help you?"}]
        },
        {
            "role": "user",
            "parts": [{"text": "Tell me about AI"}]
        }
    ]
}
```

### Roles
- `user` - User messages
- `model` - Assistant/AI responses
- `system` - System instructions (in `system_instruction` field)

## Function Call Flow

### 1. Model Requests Function
```json
{
    "contents": [
        {
            "role": "model",
            "parts": [
                {
                    "functionCall": {
                        "name": "get_weather",
                        "args": {
                            "location": "New York"
                        }
                    }
                }
            ]
        }
    ]
}
```

### 2. Provide Function Response
```json
{
    "contents": [
        {
            "role": "user",
            "parts": [
                {
                    "functionResponse": {
                        "name": "get_weather",
                        "response": {
                            "temperature": "72°F",
                            "condition": "Sunny"
                        }
                    }
                }
            ]
        }
    ]
}
```

## Code Examples

### cURL
```bash
curl --location --request POST 'https://api.uniapi.io/gemini/v1beta/models/gemini-2.5-flash:generateContent' \
--header 'x-goog-api-key: YOUR_API_KEY' \
--header 'Content-Type: application/json' \
--data-raw '{
    "contents": [
        {
            "parts": [
                {
                    "text": "Hello, how are you?"
                }
            ]
        }
    ]
}'
```

### JavaScript (Fetch)
```javascript
fetch('https://api.uniapi.io/gemini/v1beta/models/gemini-2.5-flash:generateContent', {
    method: 'POST',
    headers: {
        'x-goog-api-key': 'YOUR_API_KEY',
        'Content-Type': 'application/json'
    },
    body: JSON.stringify({
        contents: [{
            parts: [{
                text: 'Hello, how are you?'
            }]
        }]
    })
})
.then(response => response.json())
.then(data => console.log(data));
```

### Python (Requests)
```python
import requests

url = "https://api.uniapi.io/gemini/v1beta/models/gemini-2.5-flash:generateContent"
headers = {
    "x-goog-api-key": "YOUR_API_KEY",
    "Content-Type": "application/json"
}
data = {
    "contents": [{
        "parts": [{
            "text": "Hello, how are you?"
        }]
    }]
}

response = requests.post(url, json=data, headers=headers)
print(response.json())
```

## Complete Examples

### Example 1: Text Generation
```json
{
    "contents": [
        {
            "parts": [
                {
                    "text": "Write a story about a magic backpack."
                }
            ]
        }
    ]
}
```

### Example 2: Image Understanding
```json
{
    "contents": [
        {
            "parts": [
                {
                    "text": "Describe this image"
                },
                {
                    "inline_data": {
                        "mime_type": "image/jpeg",
                        "data": "BASE64_IMAGE_DATA"
                    }
                }
            ]
        }
    ]
}
```

### Example 3: Structured Output
```json
{
    "contents": [
        {
            "parts": [
                {
                    "text": "List 5 popular cookie recipes"
                }
            ]
        }
    ],
    "generationConfig": {
        "response_mime_type": "application/json",
        "response_schema": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "recipe_name": {"type": "string"},
                    "ingredients": {
                        "type": "array",
                        "items": {"type": "string"}
                    }
                }
            }
        }
    }
}
```

### Example 4: Function Calling
```json
{
    "system_instruction": {
        "parts": {
            "text": "You are a helpful assistant with access to a weather API."
        }
    },
    "tools": [
        {
            "functionDeclarations": [
                {
                    "name": "get_weather",
                    "description": "Get weather for a location",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "location": {
                                "type": "string",
                                "description": "City name"
                            }
                        },
                        "required": ["location"]
                    }
                }
            ]
        }
    ],
    "tool_config": {
        "function_calling_config": {
            "mode": "auto"
        }
    },
    "contents": [
        {
            "role": "user",
            "parts": [
                {
                    "text": "What's the weather in Tokyo?"
                }
            ]
        }
    ]
}
```

### Example 5: Text-to-Speech
```json
{
    "contents": [
        {
            "parts": [
                {
                    "text": "Hello! Welcome to our service."
                }
            ]
        }
    ],
    "generationConfig": {
        "responseModalities": ["AUDIO"],
        "speechConfig": {
            "voiceConfig": {
                "prebuiltVoiceConfig": {
                    "voiceName": "Kore"
                }
            }
        }
    }
}
```
**Note**: Use `gemini-2.5-flash-preview-tts` model for TTS

### Example 6: Image Generation
```json
{
    "contents": [
        {
            "role": "user",
            "parts": [
                {
                    "text": "Draw a cute cat"
                }
            ]
        }
    ],
    "generationConfig": {
        "responseModalities": ["Text", "Image"]
    }
}
```
**Note**: Use `gemini-2.5-flash-image` model for image generation

## Document Processing

### Supported Document MIME Types
- PDF: `application/pdf`
- JavaScript: `application/x-javascript`, `text/javascript`
- Python: `application/x-python`, `text/x-python`
- TXT: `text/plain`
- HTML: `text/html`
- CSS: `text/css`
- Markdown: `text/md`
- CSV: `text/csv`
- XML: `text/xml`
- RTF: `text/rtf`

## Advanced Features

### Thinking/Reasoning Mode
```json
{
    "generationConfig": {
        "thinkingConfig": {
            "includeThoughts": true,
            "thinkingBudget": 1000
        }
    }
}
```

## Response Format

### Success Response
```json
{
    "candidates": [
        {
            "content": {
                "parts": [
                    {
                        "text": "Generated response text"
                    }
                ],
                "role": "model"
            },
            "finishReason": "STOP",
            "safetyRatings": []
        }
    ],
    "promptFeedback": {
        "safetyRatings": []
    }
}
```

### Error Response
```json
{
    "error": {
        "code": 400,
        "message": "Error description",
        "status": "INVALID_ARGUMENT"
    }
}
```

## Best Practices

1. **API Key Security**: Never expose your API key in client-side code
2. **Error Handling**: Always implement proper error handling
3. **Rate Limiting**: Respect API rate limits
4. **Content Moderation**: Check safety ratings in responses
5. **Token Management**: Monitor token usage to avoid exceeding limits
6. **Streaming**: Use streaming for long-form content generation
7. **Function Calling**: Validate function arguments before execution

## Limitations and Notes

- Maximum file size for inline data: Check current API limits
- Rate limits apply based on your subscription tier
- Some features may require specific model versions
- TTS requires specialized models (`gemini-2.5-flash-preview-tts`)
- Image generation requires specialized models (`gemini-2.5-flash-image`)

## Support and Resources

- **Documentation**: https://api-docs.uniapi.ai
- **API Status**: Check UniAPI.io status page
- **Support**: Contact UniAPI.io support team

---
**Last Updated**: 2026-02-15
**API Version**: v1beta
**Provider**: UniAPI.io (Google Gemini Integration)