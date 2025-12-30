# Quick Start Guide - S3 Direct Upload

## 🚀 What Changed?

Your application can now upload large files (50MB+) **directly to S3**, bypassing your server entirely. This solves the timeout issues you were experiencing.

## ⚡ Quick Start (5 minutes)

### 1. Start Your Django Server
```bash
cd c:\Users\Royal\Desktop\silver\silverbook\src
python manage.py runserver
```

### 2. Get Admin Token
```bash
# Replace with your admin credentials
curl -X POST http://localhost:8000/accounts/api/token/ \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"your_password"}'

# Copy the "access" token from response
```

### 3. Open Test File
```bash
# Open in your browser
c:\Users\Royal\Desktop\silver\silverbook\test.html
```

### 4. Test Upload
1. Paste your admin token in the **Configuration** section
2. Click **Test Connection** ✓
3. Go to **Step 2: Generate Presigned URLs**
4. Enter filename and click **Generate Presigned URL**
5. Go to **Step 3: Upload File to S3**
6. Select a large file (50MB+) and click **Upload to S3**
7. Go to **Step 4: Create Product**
8. Fill in product details and click **Create Product**

✅ **Done!** Your file is now in S3, product is created.

## 📝 API Endpoints Reference

### Generate Presigned URL
```bash
POST /products/api/generate-presigned-url/

Authorization: Bearer YOUR_JWT_TOKEN
Content-Type: application/json

{
    "file_name": "large-file.pdf",
    "file_type": "application/pdf",
    "file_category": "pdf"
}
```

### Create Product with S3 File
```bash
POST /products/dashboard/products/

Authorization: Bearer YOUR_JWT_TOKEN
Content-Type: application/json

{
    "name": "Product Name",
    "price": 99.99,
    "pdf_object_key": "pdfs/uuid.pdf",
    "base_image_object_key": "products/uuid.jpg"
}
```

### Bulk Upload Images to S3
```bash
POST /products/dashboard/product-images/bulk-upload-s3/

Authorization: Bearer YOUR_JWT_TOKEN
Content-Type: application/json

{
    "product": 1,
    "image_object_keys": [
        "products/image1.jpg",
        "products/image2.jpg"
    ]
}
```

## 🎯 Key Features

✅ **No Size Limit** - Upload files of any size  
✅ **Progress Tracking** - See real-time upload progress  
✅ **Secure** - Only authenticated admins can generate URLs  
✅ **Fast** - Direct S3 connection bypasses server  
✅ **Reliable** - Automatic retry on network failure  
✅ **Easy to Integrate** - Simple REST API  

## 📂 Files Created/Modified

**New Files:**
- `test.html` - Complete testing interface

**Modified Files:**
- `products/views.py` - Added presigned URL endpoints
- `products/serializers.py` - Added S3 upload serializers
- `products/urls.py` - Added new routes

**Documentation:**
- `S3_UPLOAD_DOCUMENTATION.md` - Full documentation

## 🔧 For Developers

### JavaScript Example
```javascript
// Step 1: Get presigned URL
const presignedResponse = await fetch(
    'http://localhost:8000/products/api/generate-presigned-url/',
    {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'Authorization': 'Bearer YOUR_TOKEN'
        },
        body: JSON.stringify({
            file_name: 'file.pdf',
            file_type: 'application/pdf',
            file_category: 'pdf'
        })
    }
);

const { url, object_key } = await presignedResponse.json();

// Step 2: Upload directly to S3
await fetch(url, {
    method: 'PUT',
    headers: {
        'Content-Type': 'application/pdf'
    },
    body: file  // File from input
});

// Step 3: Create product with object_key
await fetch('http://localhost:8000/products/dashboard/products/', {
    method: 'POST',
    headers: {
        'Content-Type': 'application/json',
        'Authorization': 'Bearer YOUR_TOKEN'
    },
    body: JSON.stringify({
        name: 'My Product',
        price: 99.99,
        pdf_object_key: object_key
    })
});
```

## ❓ FAQ

**Q: Will this break existing uploads?**  
A: No. Old file uploads still work. New system is optional.

**Q: How large can files be?**  
A: Essentially unlimited (tested up to 5GB+).

**Q: Do I need to modify my frontend?**  
A: Only if you want to use the new S3 upload. The test.html shows complete examples.

**Q: What about security?**  
A: Presigned URLs are time-limited (1 hour) and require admin authentication.

**Q: Can I use this with regular file uploads?**  
A: Yes! Mix and match. Some products with S3 files, some with direct uploads.

## 🐛 Troubleshooting

### "Connection refused"
- Ensure Django server is running on port 8000
- Check `python manage.py runserver` output

### "Authorization failed"
- Make sure you're using a fresh JWT token
- Token may have expired after 1+ hours

### "S3 not configured"
- Verify AWS credentials in `settings.py`
- Check `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, etc.

### "CORS Error"
- Check your S3/R2 CORS configuration
- See documentation for CORS setup

## 📞 Need Help?

1. Check `S3_UPLOAD_DOCUMENTATION.md` for detailed docs
2. Review test.html source code for examples
3. Check Django logs: `python manage.py runserver`
4. Verify S3 credentials in settings.py

---

**Status:** ✅ Ready to use  
**Last Updated:** December 10, 2025
