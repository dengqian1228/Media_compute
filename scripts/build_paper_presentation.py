"""Create the paper-comparison PDF and PPTX, preserving A's latest five PDF pages.

Optional authoring dependencies: requirements-presentation.txt.
PDF retains vector originals for A. PPTX imports A pages as slide-sized pictures;
B text and images are individual editable objects. Runtime Demo needs none of
these authoring dependencies. No generated pictures are used.
"""
import argparse
import hashlib
import io
import json
from pathlib import Path
from datetime import datetime, timezone

import pymupdf
from PIL import Image
from pptx import Presentation
from pptx.util import Pt
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from reportlab.pdfgen.canvas import Canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.utils import ImageReader

ROOT=Path(__file__).resolve().parents[1]
DOCS=ROOT/'docs'
W,H=1152,648
BG='#f5f9f9';INK='#192e3b';TEAL='#125461';MUTED='#526d79'
SOURCE=DOCS/'L0_图像结构平滑与边缘提取.pdf'
TARGET=DOCS/'L0_图像结构平滑与边缘提取_全屏演示版'
PAGE='https://jiaya.me/file/archive/projects/L0smoothing/ClipArt.htm'


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p):return json.loads(Path(p).read_text())
def rgb(s):return tuple(int(s[i:i+2],16)/255 for i in (1,3,5))


class Slides:
    def __init__(self,font):
        pdfmetrics.registerFont(TTFont('Chinese',str(font),subfontIndex=0))
        self.buffer=io.BytesIO();self.pdf=Canvas(self.buffer,pagesize=(W,H))
        self.ppt=Presentation();self.ppt.slide_width=Pt(W);self.ppt.slide_height=Pt(H)
        self.assets=[];self.texts=[];self.page_text=[]
    def text(self,x,y,w,h,s,size=21,color=INK,bold=False):
        # Top-left coordinates. Use identical explicit line breaks in PDF/PPTX.
        self.pdf.setFillColorRGB(*rgb(color));self.pdf.setFont('Chinese',size)
        for i,line in enumerate(s.split('\n')):self.pdf.drawString(x,H-y-size-i*size*1.35,line)
        tb=self.slide.shapes.add_textbox(Pt(x),Pt(y),Pt(w),Pt(h));tf=tb.text_frame
        tf.margin_left=tf.margin_right=tf.margin_top=tf.margin_bottom=0
        for i,line in enumerate(s.split('\n')):
            p=tf.paragraphs[0] if i==0 else tf.add_paragraph();p.text=line;p.font.name='Microsoft YaHei';p.font.size=Pt(size);p.font.bold=bold;p.font.color.rgb=RGBColor.from_string(color[1:]);p.space_after=Pt(size*.25)
        self.page_text.append(s)
    def rect(self,x,y,w,h,color):
        self.pdf.setFillColorRGB(*rgb(color));self.pdf.rect(x,H-y-h,w,h,stroke=0,fill=1)
        shape=self.slide.shapes.add_shape(MSO_SHAPE.RECTANGLE,Pt(x),Pt(y),Pt(w),Pt(h));shape.fill.solid();shape.fill.fore_color.rgb=RGBColor.from_string(color[1:]);shape.line.fill.background()
    def image(self,path,x,y,w,h,roi=None,label=None):
        with Image.open(path) as im:
            im=im.convert('RGB')
            if roi:im=im.crop(roi)
            iw,ih=im.size;ratio=min(w/iw,h/ih);dw,dh=iw*ratio,ih*ratio
            stream=io.BytesIO();im.save(stream,format='PNG');raw=stream.getvalue()
        dx=x+(w-dw)/2;dy=y+(h-dh)/2
        self.pdf.drawImage(ImageReader(io.BytesIO(raw)),dx,H-dy-dh,dw,dh)
        self.slide.shapes.add_picture(io.BytesIO(raw),Pt(dx),Pt(dy),width=Pt(dw),height=Pt(dh))
        self.assets.append({'page':self.number,'source':str(Path(path).relative_to(ROOT)),'sha256':sha(path),'roi_xyxy':roi,'label':label})
    def start(self,n,title,seconds):
        self.number=n;self.page_text=[];self.slide=self.ppt.slides.add_slide(self.ppt.slide_layouts[6]);self.rect(0,0,W,H,BG)
        if title:self.text(48,26,1060,55,f'{n:02d} · {title}',31,TEAL,True)
    def end(self,notes):
        self.slide.notes_slide.notes_text_frame.text=notes
        self.texts.append({'page':self.number,'text':self.page_text,'notes':notes});self.pdf.showPage()


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--experiment',type=Path,required=True);p.add_argument('--video',type=Path,default=DOCS/'media/demo_three_sections_fullscreen.mp4');p.add_argument('--output-stem',type=Path,default=TARGET);p.add_argument('--font',type=Path,default=Path('/usr/share/fonts/truetype/wqy/wqy-microhei.ttc'));a=p.parse_args()
    kind=load(a.video.resolve().with_suffix('.json')).get('demo_kind')
    three=kind=='three_sections'
    course=kind in ('course_tasks','three_sections')
    target=a.output_stem.resolve();out=a.experiment.resolve();experiment=load(out/'experiment.json');manifest=load(out/'source_manifest.json')
    for name,digest in experiment['artifacts'].items():assert sha(out/name)==digest,name
    deck=Slides(a.font);original=pymupdf.open(SOURCE)
    assert len(original)==10
    # Preserve A's slide appearance in PPTX without changing A's original PDF.
    for i in range(5):
        s=deck.ppt.slides.add_slide(deck.ppt.slide_layouts[6]);png=original[i].get_pixmap(matrix=pymupdf.Matrix(2,2)).tobytes('png')
        s.shapes.add_picture(io.BytesIO(png),0,0,width=Pt(W),height=Pt(H));s.notes_slide.notes_text_frame.text='成员 A 原版第'+str(i+1)+'页，按最新PDF完整导入为图片；内容未改。'
    def row(case,lam=.008):return next(r for r in experiment['rows'] if r['case']==case and r['lambda']==lam)
    def paths(c):return [out/c['id']/c['files']['input']['file'],out/c['id']/c['files']['author']['file'],out/row(c['id'])['output']]
    c1,c2=manifest['cases'];cols=[48,416,784];cw=320
    deck.start(6,'Clip-art JPEG 去伪影：数据与比较方法',50)
    for c,x in [(c1,48),(c2,350)]:
        deck.text(x,98,275,35,c['title']+' · 官网原始 JPEG',20,TEAL,True);deck.image(paths(c)[0],x,141,275,200,label='author website input')
    deck.rect(670,104,434,235,'#e4f0ef')
    deck.text(691,120,390,190,'同一个输入，比较两种输出\n\n作者公开结果：直接下载\n本组结果：本组 L0 算法\n不缩放、不重新编码输入',22)
    deck.text(48,365,1060,100,'实验：2 幅原尺寸图 × 4 档 λ（0.002 / 0.008 / 0.02 / 0.08）\n本组固定 κ=2、βmax=100000；全图与同一局部分别比较。',23)
    deck.rect(48,465,1056,89,'#fff1d9');deck.text(66,478,1018,72,('作者输出不是干净真值：PSNR / SSIM 仅衡量与作者结果的一致程度。\n公开原始素材另做受控JPEG实验；真值评价与作者一致性分开。' if course else '作者输出不是干净真值：PSNR / SSIM 仅衡量与作者结果的一致程度。\nJPEG 质量、作者逐图参数未公开；不能据一致性指标声称恢复质量更高。'),19)
    deck.text(48,576,1060,25,'来源：Xu 等（2011）项目官网 · Clip-Art Compression Artifact Removal Examples',14,MUTED)
    deck.end('实验采用论文官网公开的西瓜与蜗牛Clip-art素材。输入与作者输出成对下载，本组只运行自己的核心。作者没有提供干净真值，后面的数值只能解释为与作者结果的一致程度。')

    deck.start(7,'西瓜：作者结果与本组结果的同图对照',55)
    for x,path,label in zip(cols,paths(c1),['官网 JPEG 输入','作者公开结果（非真值）','本组 L0 · λ=0.008']):
        deck.text(x,94,cw,30,label,20,TEAL,True);deck.image(path,x,133,cw,207,label=label);deck.image(path,x,365,cw,169,c1['roi_xyxy'],label+' / ROI')
    r=row('9')
    deck.text(48,341,1060,22,'下排：三列使用相同局部，观察眼睛、眉毛与轮廓附近的压缩杂色。',16,MUTED)
    deck.text(48,548,1060,55,f'本组相对作者：全图 {r["author_psnr_db"]:.2f} dB / SSIM {r["author_ssim"]:.4f}；局部 {r["author_roi_psnr_db"]:.2f} dB / {r["author_roi_ssim"]:.4f}\n边缘附近的杂色减轻，主要轮廓接近；细小边界仍有差异。数值不代表真值恢复质量。',17)
    deck.end('先按列讲官网JPEG、作者输出、本组输出，再看下排同一区域。可以观察到两种输出都抑制了背景和轮廓附近杂色；本组与作者并非逐像素一致。报全图一致性指标即可，强调作者输出不是干净真值，不能宣称超过论文。')

    deck.start(8,'蜗牛：作者对照与平滑强度的影响',55)
    for x,path,label in zip(cols,paths(c2),['官网 JPEG 输入','作者公开结果（非真值）','本组 L0 · λ=0.008']):
        deck.text(x,94,cw,30,label,20,TEAL,True);deck.image(path,x,130,cw,200,label=label)
    for x,path,label in zip(cols,[paths(c2)[1],paths(c2)[2],out/row('20',.08)['output']],['作者：同一局部','本组 λ=0.008：同一局部','本组 λ=0.08：同一局部']):
        deck.text(x,343,cw,28,label,17,TEAL);deck.image(path,x,376,cw,151,c2['roi_xyxy'],label)
    r=row('20');strong=row('20',.08)
    deck.text(48,544,1060,65,f'相对作者全图：λ=0.008 → {r["author_psnr_db"]:.2f} dB / {r["author_ssim"]:.4f}；λ=0.08 → {strong["author_psnr_db"]:.2f} dB / {strong["author_ssim"]:.4f}\n强平滑使螺旋轮廓变形、细节减少。越平整不等于越接近作者，更不等于恢复真值。',17)
    deck.end('蜗牛默认参数的结果与作者公开输出很接近，但不能据此推断作者使用同样参数。下排第三张展示本组λ=0.08的结果，三张图使用相同ROI。指出螺旋和白色细边的变化；不要把与作者输出更接近直接说成质量更好。通过同一论文素材的不同参数，说明强平滑也会改变原有轮廓。')

    video=a.video.resolve()
    video_record=load(video.with_suffix('.json'));poster=video.with_suffix('.png')
    assert sha(video)==video_record['video_sha256']
    assert sha(poster)==video_record['poster_sha256']
    duration=video_record['duration_seconds']
    dynamic=video_record.get('demo_kind') in ('precomputed_parameter_sweeps','course_tasks','three_sections')
    deck.start(9,None,75)
    # The movie and its poster fill the slide; the prepared 16:9 media preserves
    # the entire recording without stretching. PDF uses the same static poster.
    assert abs(video_record['width']/video_record['height']-W/H)<1e-6, 'Prepare a 16:9 video with scripts.prepare_fullscreen_video first'
    deck.image(poster,0,0,W,H,label='全页视频封面')
    deck.slide.shapes.add_movie(str(video),0,0,Pt(W),Pt(H),poster_frame_image=str(poster),mime_type='video/mp4')
    deck.end(f'本页播放{duration:.2f}秒预录演示，总预算75秒。'+('依次展示三个部分：沙滩结构平滑使用全图，砖墙同参Canny使用相同局部，论文官网西瓜与蜗牛对照使用相同局部。每段真实拖动完整参数序列，论文两图分别经过全部45档λ。左侧输入和作者输出固定，右侧本组结果变化；强平滑可能损伤轮廓。全部图像为本组真实预计算，没有插值；录像不包含读写复现或OpenMoji素材。' if three else '四页分别对应结构平滑、读写复现、同参Canny、JPEG与指标。参数和迭代使用真实预计算帧；读写页在录制时实际运行RGB/灰度输入、保存并重算，像素差0。受控JPEG使用OpenMoji公开原始作品作为干净参考，论文输出另作一致性对照。西瓜和蜗牛均放大同一局部，固定κ=2依次展示λ=.001/.008/.08；左两列固定，右列变化，强平滑用于说明轮廓损失。' if course else '画面展示参数滑块切换本组预计算结果，不进行现场计算或图像插值。先讲A的λ与κ变化、固定参数Canny，再讲B的论文Clip-art的λ与κ变化。' if dynamic else '录制中真实调用本组CLI并查看本次生成的结果。')+f'放映时点击画面播放；若PowerPoint/WPS无法播放嵌入视频，直接打开docs/media/{video.name}。PDF只显示封面。视频无声，由本人同步讲解。')

    deck.start(10,None,35)
    message='谢谢大家';size=64
    deck.pdf.setFillColorRGB(*rgb(TEAL));deck.pdf.setFont('Chinese',size)
    deck.pdf.drawCentredString(W/2,(H-size)/2+8,message)
    box=deck.slide.shapes.add_textbox(0,0,Pt(W),Pt(H));tf=box.text_frame
    tf.margin_left=tf.margin_right=tf.margin_top=tf.margin_bottom=0
    tf.vertical_anchor=MSO_ANCHOR.MIDDLE
    paragraph=tf.paragraphs[0];paragraph.text=message;paragraph.alignment=PP_ALIGN.CENTER
    paragraph.font.name='Microsoft YaHei';paragraph.font.size=Pt(size);paragraph.font.bold=True
    paragraph.font.color.rgb=RGBColor.from_string(TEAL[1:])
    deck.page_text.append(message)
    deck.end('谢谢大家。结束讲解，准备回答问题；分工与用时只保留在讲稿中。')
    deck.pdf.save();bpdf=pymupdf.open(stream=deck.buffer.getvalue(),filetype='pdf')
    final=pymupdf.open();final.insert_pdf(original,from_page=0,to_page=4);final.insert_pdf(bpdf)
    final.save(target.with_suffix('.pdf'));deck.ppt.save(target.with_suffix('.pptx'))
    new=pymupdf.open(target.with_suffix('.pdf'))
    for i in range(5):assert original[i].get_pixmap().samples==new[i].get_pixmap().samples
    for i in range(5,10):
        if i!=8:assert new[i].get_text().strip()
        new[i].get_pixmap(matrix=pymupdf.Matrix(.8,.8)).save(DOCS/f'paper_slide_{i+1}_preview.png')
    ppt=Presentation(target.with_suffix('.pptx'));assert len(ppt.slides)==10
    # Fit text boxes and pictures to slide canvas; PDF inspected separately.
    for slide in ppt.slides:
        for shape in slide.shapes:
            assert shape.left>=0 and shape.top>=0
            assert shape.left+shape.width<=ppt.slide_width+Pt(1)
            assert shape.top+shape.height<=ppt.slide_height+Pt(1)
    evidence={'generated_at':datetime.now(timezone.utc).isoformat(),'source_pdf':str(SOURCE.relative_to(ROOT)),'source_pdf_sha256':sha(SOURCE),'experiment':str(out.relative_to(ROOT)),'experiment_sha256':sha(out/'experiment.json'),'slides':10,'speaker_seconds':{'A':270,'B':270},'pdf_first_five_pages_render_identical':True,'pptx_A_pages':'raster imports from original PDF; not editable text','pptx_B_pages':'editable text, individually embedded images','font_used':str(a.font),'assets':deck.assets,'pdf_sha256':sha(target.with_suffix('.pdf')),'pptx_sha256':sha(target.with_suffix('.pptx')),'embedded_video':{'path':str(video.relative_to(ROOT)),'sha256':sha(video),'duration_seconds':duration,'slide':9,'full_slide':True},'visible_member_b_footers':False,'closing_text':'谢谢大家'}
    (DOCS/('presentation_course_assets.json' if course else 'presentation_dynamic_assets.json' if dynamic else 'presentation_paper_assets.json')).write_text(json.dumps(evidence,ensure_ascii=False,indent=2)+'\n')
    notes=['# 论文官网对照版：成员 B 讲稿\n\n成员A讲解第1—5页，成员B讲解第6—10页。B部分建议各50、55、55、75、35秒，共270秒；全场9分钟预算，最后一页用于致谢和预留时间。\n\n本稿待两人核对和排练，不是已发生的展示记录。\n']
    for page in deck.texts:notes.append(f'\n## 第{page["page"]}页\n\n'+page['notes']+'\n')
    notes.append('\n## 来源与运行证据\n\n- [论文官网素材页]('+PAGE+')\n- [输入清单](../data/paper_clipart/manifest.json)\n- [实验说明](paper_comparison.md)\n- [离线结果页](../'+str(out.relative_to(ROOT))+'/index.html)\n- [逐图来源与导出检查](presentation_paper_assets.json)\n- [第9页演示视频](media/'+video.name+')\n- [视频播放说明](demo_video.md)\n')
    notes_text=''.join(notes)
    if dynamic:notes_text=notes_text.replace('presentation_paper_assets.json','presentation_dynamic_assets.json').replace('demo_video.md','demo_dynamic.md')
    if course:notes_text=notes_text.replace('presentation_dynamic_assets.json','presentation_course_assets.json').replace('demo_dynamic.md','demo_course.md')
    (DOCS/('presentation_course_notes.md' if course else 'presentation_dynamic_notes.md' if dynamic else 'presentation_paper_notes.md')).write_text(notes_text,encoding='utf-8')
    print(target.with_suffix('.pdf'));print(target.with_suffix('.pptx'))

if __name__=='__main__':main()
