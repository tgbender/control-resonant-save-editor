"""Pure Python CityHash64 for deterministic identifier research.

Algorithm adapted from Google's city.cc (Geoff Pike and Jyrki Alakuijala).
Copyright (c) 2011 Google, Inc.

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:
The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.
"""
MASK = (1 << 64) - 1
K0 = 0xc3a5c85c97cb3127
K1 = 0xb492b66fbe98f273
K2 = 0x9ae16a3b2f90404f

def rotate(x, n):
    x &= MASK
    return ((x >> n) | (x << (64-n))) & MASK

def mix(x):
    x &= MASK
    return x ^ (x >> 47)

def swap(x): return int.from_bytes((x & MASK).to_bytes(8, 'little'), 'big')

def h16(a, b, mul=0x9ddfea08eb382d69):
    a = mix(((a & MASK) ^ (b & MASK)) * mul)
    b = mix(((b & MASK) ^ a) * mul)
    return b * mul & MASK

def cityhash64(s):
    if isinstance(s, str): s = s.encode('utf8')
    n = len(s)
    def f(offset): return int.from_bytes(s[offset:offset+8], 'little')
    mul = (K2 + n * 2) & MASK
    if n <= 16:
        if n >= 8:
            a = (f(0) + K2) & MASK; b = f(n-8)
            return h16(rotate(b,37)*mul+a, (rotate(a,25)+b)*mul, mul)
        if n >= 4:
            return h16(n+(int.from_bytes(s[:4],'little')<<3), int.from_bytes(s[n-4:],'little'),mul)
        if n:
            y = s[0] + (s[n >> 1] << 8); z = n + (s[n-1] << 2)
            return mix((y*K2 & MASK) ^ (z*K0 & MASK))*K2 & MASK
        return K2
    if n <= 32:
        a=f(0)*K1&MASK; b=f(8); c=f(n-8)*mul&MASK; d=f(n-16)*K2&MASK
        return h16(rotate(a+b,43)+rotate(c,30)+d,a+rotate(b+K2,18)+c,mul)
    if n <= 64:
        a=f(0)*K2&MASK; b=f(8); c=f(n-24); d=f(n-32)
        e=f(16)*K2&MASK; ff=f(24)*9&MASK; g=f(n-8); h=f(n-16)*mul&MASK
        u=(rotate(a+g,43)+(rotate(b,30)+c)*9)&MASK
        v=(((a+g)&MASK)^d)+ff+1
        w=(swap((u+v)*mul)+h)&MASK
        x=(rotate(e+ff,42)+c)&MASK
        y=(swap((v+w)*mul)+g)*mul&MASK
        z=(e+ff+c)&MASK
        a=(swap((x+z)*mul+y)+b)&MASK
        b=mix((z+a)*mul+d+h)*mul&MASK
        return (b+x)&MASK
    def weak(offset,a,b):
        w,x,y,z=(f(offset+i) for i in (0,8,16,24))
        a=(a+w)&MASK; b=rotate(b+a+z,21); c=a
        a=(a+x+y)&MASK; b=(b+rotate(a,44))&MASK
        return (a+z)&MASK,(b+c)&MASK
    x=f(n-40); y=(f(n-16)+f(n-56))&MASK; z=h16(f(n-48)+n,f(n-24))
    v=weak(n-64,n,z); w=weak(n-32,y+K1,x); x=(x*K1+f(0))&MASK
    for p in range(0,(n-1)&~63,64):
        x=rotate(x+y+v[0]+f(p+8),37)*K1&MASK
        y=rotate(y+v[1]+f(p+48),42)*K1&MASK
        x^=w[1]; y=(y+v[0]+f(p+40))&MASK; z=rotate(z+w[0],33)*K1&MASK
        v=weak(p,v[1]*K1,x+w[0]); w=weak(p+32,z+w[1],y+f(p+16)); z,x=x,z
    return h16(h16(v[0],w[0])+mix(y)*K1+z,h16(v[1],w[1])+x)
