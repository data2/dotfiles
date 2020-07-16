#/usr/bin/python
# Copyright (c) 2011, 2013-2016, 2018 OptumSoft, Inc.  All rights reserved.
# OptumSoft, Inc. Confidential and Proprietary.

# Load this script into your gdb session to pretty print
# many tac structures, including strings, names,
# smart pointers, entities collections and iterators.
# This is not complete yet, and may fail in some cases
# with strange error messages. It does not depend in genericIf
# but only on debug symbols, and in some cases heuristics
# to figure out the correct way to print data
#
# Add 
#    source /usr/share/tacc/gdb/tacgdb.py
# to your .gdbinit to always load this module. It has been tested
# with gdb 7.5.
#
# You should also add
#
#    set print pretty on
#    set print static-members off
#
# and if you want to see some of the supressed data use
#
#    set print taccDetails on
#
# Once set any print command will use the pretty printers defined
# here, unless you use the /r (for raw) option, as in 
#
#    p/r *a
# 



import re, gdb, os, posixpath, sys

tacInitialized=0
def initTaccTypes():
   global std_string_type
   global Tac_String_type
   global Tac_Name_type
   global int_type
   global char_type
   global char_pointer_type
   global tacInitialized
   global void_type
   global void_pointer_type
   global dir_type
   global dir_pointer_type
   global ent_type
   global ent_pointer_type
   try:
      std_string_type=gdb.lookup_type("std::string")
   except:
      pass
   try: 
      Tac_String_type=gdb.lookup_type("Tac::String")
      Tac_Name_type=gdb.lookup_type("Tac::Name")
      int_type=gdb.lookup_type("int")
      char_type=gdb.lookup_type("char")
      void_type=gdb.lookup_type("void")
      ent_type=gdb.lookup_type("Tac::Entity")
      ent_pointer_type=ent_type.pointer()
      void_pointer_type=void_type.pointer()
      char_pointer_type=char_type.pointer()
      dir_type=gdb.lookup_type("Tac::Dir")
      dir_pointer_type=dir_type.pointer()
      tacInitialized=1
   except RuntimeError as e:
      #print "Unexpected error:", e 
      # FixMe: it happens that lookup_type throws an exception.
      # this can have very annoying repercusion when debugging with gdb
      # e.g. it shows a python exception when trying to print the name
      # of a field.
      # Not sure how to fix that though. 
      pass

def baseType(type):
   """ Returns the base type of type.  This iterates over the fields
   of the type to find the base class.  Also uses some hard-coded lookups,
   since GDB doesn't seem to get everything."""
   global ent_type
   if not type:
      return None
   if str(type)=="OTacc::OConstraint":
      return ent_type
   if str(type)=="OTacc::ImperNode":
      return gdb.lookup_type("OTacc::OConstraint")
   if str(type)=="OTacc::Func":
      return gdb.lookup_type("OTacc::ImperNode")
   for f in type.fields():
      if f.is_base_class:
         return f.type
   return None
   
def fullNameForVal(val):
   """ For a given gdb.value, returns the fullname.  If the name does not start
   with /, there is an unprinatble parent above.  For Notifiees, returns the fullName of their notifier."""
   global ent_type
   name = nameForVal(val)
   if name == '"/"':
      return "/"
   if name.find("/") != -1:
      name = '"' + str(name) + '"'
      
   fullName = "/" + str(name)[1:-1]
   if isTacNotifiee(val.type):
      btName = str(baseType(val.type))
      btName = btName.replace("::NotifieeConst","");
      btName = btName.replace("::Notifiee","");
      # Hack in order to get the correct type of the notifier, since
      # GDB doesn't seem to use the dynamic type
      if not btName or btName=="None": return ""
      try:
         bt = gdb.lookup_type(btName)
      except RuntimeError:
         bt = None
      if 'notifier_' in val.type.fields():
         val = val['notifier_']['rawPtr_'].cast(bt.pointer()).dereference()
      else:
          return ""
      
   if isEntityType(val.type) or "parent_" in [x.name for x in val.type.fields()]:
      p = None
      if isEntityType(val.type):
         p = val.cast(ent_type)['parent_']
      else :
         p = val['parent_']

      if not p:
         fullName = "/..."+fullName
         return fullName
      try:
         while p:
            name = nameForVal(p)
            p = p['parent_']
            if name.find("/") != -1 and p:
               name = '"' + name + '"'
            if not name =='"/"':
               fullName = "/" + name[1:-1] + fullName
      except:
         print('excepted!')
         pass
      # Traverse the parent directories, getting names
   else:
      if fullName == "":
         return ""
   return fullName
   
def nameForVal(val):
   """ For a given value, returns the value's name.  Should work with Smart
   pointers, raw pointers, notifiees (uses notifier's name), and dereferenced
   pointers."""
   if str(val.type)[0:9]=="Tac::Ptr<":
      return nameForVal(val['rawPtr_'].cast(val.type.template_argument(0).pointer()).dereference())
   if isTacNotifiee(val.type):
      # FixMe: Assumes notifier has a name
      # FixMe: Theoreticallly we should be able to get the dynamic type
      #   of notifier, is this supported?
      
      btName = str(baseType(val.type))
      btName = btName.replace("::NotifieeConst","");
      btName = btName.replace("::Notifiee","");
      if not btName or btName=="None": return ""
      try:
         bt = gdb.lookup_type(btName)
         # FixMe: This is a hack to get around the lack of runtime type information
      except RuntimeError:
         bt = None

      while bt and ('name_' not in [x.name for x in bt.fields()]):
         bt = baseType(bt)
      if not bt:
         bt = dir_type
         # FixMe: Hack
      if 'notifier_' in val.type.fields():
         return str(val['notifier_']['rawPtr_'].cast(bt.pointer()).dereference()['name_'])
      else:
         return ""
   if val.type.code == gdb.TYPE_CODE_PTR:
      val = val.dereference()
   if typeHasName(val.type):
      bt = typeHasName(val.type)
      return str(val.address.cast(bt.pointer()).dereference()['name_'])
   return '' # No name available

def isEntityType(type):
   """ Returns whether the given type is an Entity """
   if str(type)=="Tac::Entity":
      return True
   if baseType(type):
      if isEntityType(baseType(type)):
         return True
   return False

def typeHasName(type):
   """ Returns the base type of the given type with a name_ field"""
   if str(type)=="Tac::Entity":
      # FixMe: Hack Hack Hack
      # Return Dir here since Entity no longer has name
      return dir_type
   bt = type
   while bt and ('name_' not in [x.name for x in bt.fields()]):
      bt = baseType(bt)
   return bt

# convert a Tac::Name, Tac::String or std::string to 
# a python string
def getString(a):
  global std_string_type 
  global Tac_String_type 
  t=a.type.unqualified()
  if t.code==gdb.TYPE_CODE_REF:
     t = t.target().unqualified()
     a = a.cast(t)
  t = str(t)
  if t=="Tac::Name" or t=="Tac::String8" or t=="Tac::String" or t=="Tac::MutableString":
     # FixMe: does not handle zeros in strings correctly
     hasArrayPtr = a['data_']['ctrl_']&0x40;
     if not hasArrayPtr:
        s = a['data_']['ssb_'].string(errors="ignore")
     else:
        s = str(a['data_']['arrayPtr_'].dereference()['data_'])
     size = int(a['data_']['size_'])
     q = s.find('"')
     if q>0:
        s = s[q+1:-1]
     ##### the str representation usually is enclosed by "", cut that off
     return s[0:size]
     #### Truncate to the correct size

  #print a.type.tag
  return a['_M_dataplus']['_M_p'].string()


# print all fields of a type
def printFields(type):
   print("fields for ",type," ",type.code,len(type.fields()))
   for i in type.fields():
      print(i.name, i.type," // ",type.code)


def getTemplateParams(type):
   # Return the template parameters of a type in a list of strings. 
   # For Example :
   # Given type:
   # Tac::DynArrayQueue<Tac::NboAttrLog::LogOffset, unsigned int>)
   # return value: 
   # ['Tac::NboAttrLog::LogOffset', 'unsigned int'] = 
   type=str(type)
   args=[]
   prefix=1
   ltcnt=0
   cur=""

   for x in type[:]:
      if x=='<' and prefix:
         prefix=0
         cur=""
      elif x==',' and ltcnt==0:
         args.append(cur)
         cur=""
      elif x=='>' and ltcnt==0:
         args.append(cur)
         return args
      elif x=='>':
         ltcnt=ltcnt-1
         cur=cur+">"
      elif x=='<':
         ltcnt=ltcnt+1
         cur=cur+"<"
      elif not prefix:
         if x!=' ' or cur:
            cur=cur+x

   return args


# convert type to string, making sure smart pointer types
# are printed as one would expect in Tac
def typeToStr(type):
   t=str(type)
   if t[0:9]=="Tac::Ptr<":
      return t[9:-1]+"::Ptr"
   if t[0:14]=="Tac::ConstPtr<":
      return t[14:-1]+"::ConstPtr"
   return t

# returns a list of attributes of the given type,
# only attributes with a name ending in '_' are
# returned
def findAttrOfType(tp, attrType):
   #print "tp: ", tp
   #print "attrType: ", attrType
   r=[]
   if str(tp)=="Tac::PtrInterface": 
      return r
   attrType=attrType.strip_typedefs()
   for i in tp.strip_typedefs().fields():
      #print "i: ",i.name,i.type.strip_typedefs()
      if i.is_base_class:
         r=r+findAttrOfType(i.type,attrType)
      elif i.name[-1:]=="_" and str(i.type.strip_typedefs())==str(attrType):
         r=r+[i.name]
   return r

def findAllAttr(tp ):
   r=[]
   for i in tp.strip_typedefs().fields():
      if i.is_base_class:
         r=r+findAllAttr(i.type)
      elif i.name[-1:]=="_":
         r=r+[i.name]
   return r

# define 'set print taccDetails'
class SetPrintTaccDetails (gdb.Parameter):
   set_doc='Set printing of unimportant attributes of tacc types'
   show_doc='Show printing of unimportant attributes of tacc types'
    
   def __init__ (self):
       super (SetPrintTaccDetails, self).__init__ (
                "print taccDetails",gdb.COMMAND_DATA,gdb.PARAM_BOOLEAN)
       self.value=False

SetPrintTaccDetails()

# define dereference function for smart pointers
# (works on normal pointers too for convenience)
class DereferenceSmartPtr (gdb.Function):
   """ dereference a smart pointer"""
   def __init__ (self):
      super (DereferenceSmartPtr, self).__init__ ("D")

   def invoke(self, arg):
      try:
         return arg['rawPtr_'].dereference()
      except:
         return arg.dereference()

DereferenceSmartPtr()


class TacOrdinalNominal:
   "Print a Tac::Ordinal or Tac::Nominal"
   def __init__ (self, val):
       self.val = val
   def to_string (self):
       return self.val['value_']

class TacEntityId:
   "Print a Tac::EntityId"
   def __init__ (self, val):
      self.val = val
   def to_string (self):
      eid = hex(int(str(self.val['value_'])))
      eidLen = 2+16+1 # The length of an EID format string - 0x ..0000.. L
      if(len(eid)<eidLen):
         eid = eid[0:2]+"0"*(eidLen-len(eid))+eid[2:]
         # Pad the EID with 0s
      return eid

class TacPtrInterface:
   "Print a Tac::PtrInterface"
   def __init__ (self, val):
       self.val = val
   def to_string (self):
      return "ref:"+str(hex(int(self.val['ref_'])))
      # Print references in hexadecimal(due to flags)

class TacEntity:
   "Print a Tac::Entity"
   def __init__ (self, val):
       self.val = val
   def to_string (self):
      a = ''
      try:
         a='"'+str(getString(self.val['name_']))+'"'
         a=a+', V:'+str(self.val['version_'])
         a=a+', ref:'+str(hex(int(self.val['ref_'])))
      except:
         pass
      return a

class TacStringPrinter:
   "Print a Tac::String"
   def __init__ (self, val):
      self.val = val
   def to_string (self):
      return getString(self.val)
   def display_hint (self):
      return 'string'

class TacStringPrinter8:
   "Print a Tac::String8"
   def __init__ (self, val):
       self.val = val
   def to_string (self):
       return getString(self.val)
   def display_hint (self):
       return 'string'


class TacPointer:
   "Print a pointer to a Tac object."
   def __init__ (self, val):
      self.val = val
   def to_string (self):
      n = ""
      if self.val != 0:
         n = fullNameForVal(self.val.dereference())
      t = self.val.cast(void_pointer_type)
      return '(%s)%s %s' % (str(self.val.type), t, n )      

class TacHashMapIterator:
   "Print a HashMap iterator."
   def __init__ (self, val):
      self.val = val

   def to_string (self):
      print(self.val.type)
      n = str(val['ptr_'])
      
      return '(%s)%s %s' % (str(self.val.type), t, n )      

   
class TacSmartPtr:
   "Print a SmartPtr"
   def __init__ (self, val):
      self.val = val
   def to_string (self):
      n=''
      try:
         if (self.val['rawPtr_']!=0):
            n = nameForVal(self.val)
            val = str(self.val['rawPtr_'])
            return '%s (SmartPtr)' % (val)
         else:
            return '(%s *)0x%x (SmartPtr)' % \
                         (str(self.val.type), self.val['rawPtr_'])
      except:
         # FixMe: Can this happen?
         return '(%s *)0x%x (SmartPtr)' % \
             (str(self.val.type)[9:], self.val['rawPtr_'])

      
class TacHashMapIter:
   "Print a Tac::String"
   def __init__ (self, val):
      self.val = val

   def to_string (self):
      ptr=self.val['ptr_']
      return '%s' % (str(ptr))
      

class TacRbTreeMapElement:
   "Print an RbTreeMapElement"
   def __init__(self, val):
      self.val = val
      self.template=self.val.type.template_argument(0)

   def to_string (self):
      l=self.val['tacLeft_']['rawPtr_']
      t=l.cast(self.template.pointer()).dereference()['tacRbTreeMapElement_']
      offset=t.address.cast(char_pointer_type)-l.cast(char_pointer_type)
      p=self.val['tacParent_']
      if p:
         p=(p.cast(char_pointer_type)-offset).cast(self.template.pointer())
      
      if self.val['tacRed_']:
         c = "RED"
      else:
         c = "BLACK"
      return 'parent:(%s *)0x%x, left:(%s *)0x%x, right:(%s *)0x%x, %s ' % (
        str(self.template), p,
        str(self.template), self.val['tacLeft_']['rawPtr_'],
        str(self.template), self.val['tacRight_']['rawPtr_'],
        c)


class TacDynArray:
   "Print Array"
   lastTemplParam=re.compile(', *(-?[0-9]*)[^,]*$')

   class Iter:
      def __init__(self, val, valueType, min, size ):
         self.val=val
         self.valueType=valueType
         self.min=min
         self.cur=min
         self.max=size+min-1
         self.key=0
         self.size=size

      def __iter__(self):
         return self


      def next(self):
         if self.size==0 or self.cur>self.max:
            raise StopIteration
         if self.key==0:
            self.key=1
            return ("key",self.cur)

         self.cur=self.cur+1
         self.key=0
         return ("value", self.val['vector_'][self.cur-1-self.min])

      def __next__(self):
         return self.next()
      


   def __init__ (self, val):
      self.val = val

   def to_string (self):
      self.valueType=self.val.type.template_argument(0)

      t=str(self.val.type)
      m=self.val['min_']
      if isTacSimpleValueType(m.type.unqualified()):
         self.min = m['value_']
      else:
         self.min = m
      self.size=self.val['entries_']
      self.iter=self.Iter(self.val, self.valueType, self.min, self.size)

      if self.size==0:
         return "DYNARRAY "+typeToStr(self.valueType)+"[], members:" \
                +str(self.size)+", V:"+str(self.val['version_'])
      else:
         return "DYNARRAY "+typeToStr(self.valueType)+"["+str(self.min) \
                +".."+str(self.min+self.size-1)+"], members:"+str(self.size) \
                +", V:"+str(self.val['version_'])

   def children(self):
      return self.iter

   def display_hint (self):
        return 'map'

class TacArrayQueue:
   "Print Array Queue"
   lastTemplParam=re.compile(', *(-?[0-9]*)[^,]*$')

   class Iter:
      def __init__(self, val, valueType, headIndex, len, size ):
         self.val=val
         self.valueType=valueType
         self.headIndex=headIndex
         self.cur=0
         self.size=size
         self.len=len
         self.key=0

      def __iter__(self):
         return self

      def next(self):
         if self.cur==self.len:
            raise StopIteration
         if self.key==0:
            self.key=1
            return ("key",self.cur+self.headIndex)

         self.cur=self.cur+1
         self.key=0
         return ("value", self.val['array_'][(self.cur-1+self.headIndex)%self.size])

      def __next__(self):
         return self.next()


   def __init__ (self, val):
      self.val = val

   def to_string (self):
      self.valueType=self.val.type.strip_typedefs().template_argument(0)
      self.keyType=self.val.type.strip_typedefs().template_argument(1)
      t=getTemplateParams(self.val.type.strip_typedefs())
      self.min=t[3]
      while(self.min[-1:]<'0' or self.min[-1:]>'9'):
         self.min=self.min[0:-1]
      self.min=int(self.min)
      self.headIndex=self.val['headIndex_']['value_']
      
      self.len=self.val['size_']
      self.size=(self.val['array_'].type.sizeof
                      /self.val['array_'].dereference().type.sizeof)
      self.iter=self.Iter(self.val, self.valueType, self.headIndex, self.len, 
                           self.size)

      
      return "AQUEUE "+typeToStr(self.valueType)+"["+str(self.headIndex)+".." \
                      +str(self.headIndex+self.len-1)+"], members:"+str(self.len) \
                      +", V:"+str(self.val['version_'])

   def children(self):
      return self.iter

   def display_hint (self):
        return 'map'

class TacDynArrayQueue:
   "Print Dyn Array Queue"
   lastTemplParam=re.compile(', *(-?[0-9]*)[^,]*$')

   class Iter:
      def __init__(self,val,valueType,headIndex,len,size):
         self.val = val
         self.valueType = valueType
         self.headIndex = headIndex
         self.cur = 0
         self.size = size
         self.len = len
         self.key = 0

      def __iter__(self):
         return self

      def next(self):
         if self.cur==self.len:
            raise StopIteration
         if self.key==0:
            self.key=1
            return ("key",self.cur+self.headIndex)

         self.cur=self.cur+1
         self.key=0
         return ("value",self.val['array_'][(self.cur-1+self.headIndex)%self.size])

      def __next__(self):
         return self.next()


   def __init__ (self, val):
      self.val = val

   def to_string(self):
      self.valueType = self.val.type.strip_typedefs().template_argument(0)
      self.keyType = self.val.type.strip_typedefs().template_argument(1)
      self.headIndex = self.val['headIndex_']
      self.tailIndex = self.val['tailIndex_']
      self.len = self.tailIndex-self.headIndex
      self.size = self.val['size_']
      self.version = self.val['version_']

      self.iter = self.Iter(
            self.val,
            self.valueType,
            self.headIndex,
            self.len,
            self.size)

      return "DAQUEUE "+typeToStr(self.valueType)+"["+str(self.headIndex)+".." \
                      +str(self.headIndex+self.len-1)+"], members:"+str(self.len) \
                      +", V:"+str(self.val['version_'])

   def children(self):
      return self.iter

   def display_hint (self):
        return 'dynamic array queue'


class TacArray:
   "Print Array"
   lastTemplParam=re.compile(', *(-?[0-9]*)[^,]*$')

   class Iter:
      def __init__(self, val, valueType, min, size ):
         self.val=val
         self.valueType=valueType
         self.min=min
         self.cur=min
         self.max=size+min-1
         self.key=0

      def __iter__(self):
         return self

      def next(self):
         if self.cur>self.max:
            raise StopIteration
         if self.key==0:
            self.key=1
            return ("key",self.cur)

         self.cur=self.cur+1
         self.key=0
         return ("value", self.val['array_'][self.cur-self.min-1])

      def __next__(self):
         return self.next()


   def __init__ (self, val):
      self.val = val

   def to_string (self):
      self.valueType = self.val.type.strip_typedefs()

      t = str(self.valueType)
      m=self.lastTemplParam.search(t)
      self.min=int(m.group(1))
      self.size=(self.val['array_'].type.sizeof/
                      self.val['array_'].dereference().type.sizeof)
      self.iter=self.Iter(self.val, self.valueType, self.min, self.size)

      return "ARRAY "+typeToStr(self.valueType)+"["+str(self.min)+".." \
                      +str(self.min+self.size-1)+"], members:" \
                      +str(self.size)+", V:"+str(self.val['version_'])

   def children(self):
      return self.iter

   def display_hint (self):
        return 'map'


class TacRawList:
   "Print a Raw List"

   class Iter:
      def __init__(self, val, valueType ):
         self.val=val
         self.members=val['members_']
         self.valueType=valueType
         self.current=self.val['head_']
         self.key=0

      def __iter__(self):
         return self

      def next(self):
         if not self.current:
            raise StopIteration
         r=self.current
         self.current=r.dereference()['lrNext_']
         return ("value", str(r))

      def __next__(self):
         return self.next()


   def __init__ (self, val):
      self.val = val

   def to_string (self):
      valueType=self.val.type.template_argument(0)
      entryType=valueType
      attr=None
      self.iter=self.Iter(self.val, valueType)

      return "LIST "+typeToStr(valueType)+"[], members:" \
                      +str(self.val['members_'])+", V:" \
                      +str(self.val['version_'])

   def children(self):
      return self.iter

   def display_hint (self):
        return 'array'


class TacLinkStack:
   "Print a LinkQueue"
   entryTypeName=re.compile('\\bTac([A-Z][a-zA-Z0-9_]*)$')

   class Iter:
      def __init__(self, val, entryType, valueType, indexType, attr ):
         self.val=val
         self.members=val['members_']
         self.entryType=entryType
         self.valueType=valueType
         self.indexType=indexType
         self.attr=attr
         self.current=self.val['head_']['rawPtr_']
         self.key=0
         self.indexAttr='tac_index_'
         if self.entryType==self.valueType:
            r=findAttrOfType(self.entryType,indexType)
            if len(r)==1:
               self.indexAttr=r[0]
            else:
               self.indexAttr=None

      def __iter__(self):
         return self

      def next(self):
         if not self.current:
            raise StopIteration
         if self.key==0:
            c=self.current.cast(self.entryType.pointer()).dereference()
            self.key=1
            if self.indexAttr:
               return ("KEY",c[self.indexAttr])
            else:
               return ("KEY",'')

         r=self.current
         self.current=r.dereference()['lsNext_']['rawPtr_']
         self.key=0
         if self.entryType==self.valueType:
            return ("VALUE",str(r.cast(self.entryType.pointer())))
         else:
            return ("VALUE",str(r.cast(self.entryType.pointer())[self.attr]))

      def __next__(self):
         return self.next()


   def __init__ (self, val):
      self.val = val

   def to_string (self):
      valueType=self.val.type.template_argument(0)
      indexType=self.val.type.template_argument(1)
      entryType=valueType
      attr=None
      if valueType.tag:
         m=self.entryTypeName.search(valueType.tag)
         if m:
            name=m.group(1)
            attr=name[0].lower()+name[1:]+"_"
            for a in valueType.fields():
               if a.name==attr:
                  valueType=a.type
                  break

      self.iter=self.Iter(self.val, entryType, valueType, indexType, attr)
      return "STACK "+typeToStr(valueType)+"["+typeToStr(indexType)+"], members:" \
                      +str(self.val['members_'])+", V:"+str(self.val['version_'])

   def children(self):
      return self.iter

   def display_hint (self):
        return 'map'


class TacLinkedList:
   "Print a LinkedList"
   entryTypeName=re.compile('\\bTac([A-Z][a-zA-Z0-9_]*)$')

   class Iter:
      def __init__(self, val, entryType, valueType, attr ):
         self.val=val
         self.members=val['members_']
         self.entryType=entryType
         self.valueType=valueType
         self.attr=attr
         self.current=self.val['head_']['rawPtr_']

      def __iter__(self):
         return self

      def next(self):
         if not self.current:
            raise StopIteration

         r=self.current
         self.current=r.dereference()['llNext_']['rawPtr_']
         if self.entryType==self.valueType:
            return ("VALUE",str(r.cast(self.entryType.pointer())))
         else:
            return ("VALUE",str(r.cast(self.entryType.pointer())[self.attr]))

      def __next__(self):
         return self.next()


   def __init__ (self, val):
      self.val = val

   def to_string (self):
      valueType=self.val.type.template_argument(0)
      entryType=valueType
      attr=None
      if valueType.tag:
         m=self.entryTypeName.search(valueType.tag)
         if m:
            name=m.group(1)
            attr=name[0].lower()+name[1:]+"_"
            for a in valueType.fields():
               if a.name==attr:
                  valueType=a.type
                  break

      self.iter=self.Iter(self.val, entryType, valueType, attr)
      return "LIST "+typeToStr(valueType)+"[], members:" \
                      +str(self.val['members_'])+", V:"+str(self.val['version_'])

   def children(self):
      return self.iter

   def display_hint (self):
        return 'array'


class TacLinkQueue:
   "Print a LinkQueue"
   entryTypeName=re.compile('\\bTac([A-Z][a-zA-Z0-9_]*)$')

   class Iter:
      def __init__(self, val, entryType, valueType, indexType, attr ):
         self.val=val
         self.members=val['members_']
         self.entryType=entryType
         self.valueType=valueType
         self.indexType=indexType
         self.attr=attr
         self.current=self.val['head_']['rawPtr_']
         self.key=0
         self.indexAttr='tac_index_'
         if self.entryType==self.valueType:
            r=findAttrOfType(self.entryType,indexType)
            if len(r)==1:
               self.indexAttr=r[0]
            else:
               self.indexAttr=None

      def __iter__(self):
         return self

      def next(self):
         if not self.current:
            raise StopIteration
         if self.key==0:
            c=self.current.cast(self.entryType.pointer()).dereference()
            self.key=1
            if self.indexAttr:
               return ("KEY",c[self.indexAttr])
            else:
               return ("KEY",'')

         r=self.current
         self.current=r.dereference()['lqNext_']['rawPtr_']
         self.key=0
         if self.entryType==self.valueType:
            return ("VALUE",str(r.cast(self.entryType.pointer())))
         else:
            return ("VALUE",str(r.cast(self.entryType.pointer())[self.attr]))

      def __next__(self):
         return self.next()


   def __init__ (self, val):
      self.val = val

   def to_string (self):
      t=self.val.type;
      hasiter=1
      if t.code==gdb.TYPE_CODE_PTR:
         hasiter=0
         t=t.target()
      valueType=t.template_argument(0)
      indexType=t.template_argument(1)
      entryType=valueType
      attr=None
      if valueType.tag:
         m=self.entryTypeName.search(valueType.tag)
         if m:
            name=m.group(1)
            attr=name[0].lower()+name[1:]+"_"
            for a in valueType.fields():
               if a.name==attr:
                  valueType=a.type
                  break

      self.iter=self.Iter(self.val, entryType, valueType, indexType, attr)

      ind=typeToStr(indexType)
      if self.iter and self.iter.indexAttr:
         ind=str(self.iter.indexAttr)

      return "QUEUE "+typeToStr(valueType)+"["+ind \
                      +"], members:"+str(self.val['members_'])+", V:" \
                      +str(self.val['version_'])

   def children(self):
      return self.iter

   def display_hint (self):
      return 'map'



class TacHashMap:
   "Print a HashMap"
   entryTypeName=re.compile('\\bTac([A-Z][a-zA-Z0-9_]*)$')

   class Iter:
      def __init__(self, val, entryType, valueType, attr, indexType):
         self.val=val
         self.members=val['members_']
         self.bucket=val['bucket_']
         self.buckets=val['buckets_']
         self.entryType=entryType
         self.valueType=valueType
         self.attr=attr
         self.indexType=indexType

         self.current = 0
         self.cnt=0
         while self.current==0 and self.cnt<self.buckets:
            self.current = self.bucket[self.cnt]['rawPtr_']
            self.cnt += 1

         self.key=0
         self.indexAttr = None
         if self.entryType==self.valueType:
            r=findAttrOfType(self.entryType,indexType)
            if len(r)==1:
               self.indexAttr=r[0]
            else:
               self.indexAttr=None         

      def __iter__(self):
         return self

      def next(self):
         if not self.current or self.current==0:
            raise StopIteration
         if self.key==0:
            c=self.current.cast(self.entryType.pointer()).dereference()
            self.key=1
            if self.indexAttr:               
               return ("KEY",c[self.indexAttr])
            if "tac_index_" in [x.name for x in self.entryType.fields()]:
               return ("KEY", c["tac_index_"])
            else:
               return ("KEY",nameForVal(c))
         else:
            r=self.current
            c=self.current.cast(self.entryType.pointer()).dereference()
            self.current=c['fwkHmNext_']['rawPtr_']
            if self.current==0:
               while self.current==0 and self.cnt<self.buckets:
                  self.current=self.bucket[self.cnt]['rawPtr_']
                  self.cnt=self.cnt+1
            self.key=0
            if (self.entryType==self.valueType 
                or not gdb.parameter("print taccDetails")):
               if isTacNotifiee(c.type):
                  addr = str(r.cast(self.entryType.pointer()))
                  return ("VALUE", addr )
               else:
                  pfields = [x for x in self.entryType.fields() if not x.is_base_class and str(x.type)!="Tac::Ptr<Tac::TacAttr>" ]
                  field = [x.name for x in pfields if x.name.find("fwk")==-1 and x.name!="tac_index_"]
                  val = str(r.cast(self.entryType.pointer()))
                  if str(self.entryType)=="Tac::Dir::Entry":
                     return ("VALUE", val + ", ptr = " + str(c['tacPtr_']))
                  elif len(field)!=1:
                     return ("VALUE", val)
                     # FixMe: Just print a pointer if it's not a notifiee and has
                     # no tac_index_... is this possible?
                  else:
                     return ("VALUE", val + " " + str(c[field[0]]))
            else:
               return ("VALUE",str(c[self.attr]))

      def __next__(self):
         return self.next()


   def __init__ (self, val):
      self.val = val

   def to_string (self):
      valueType=self.val.type.template_argument(0)
      indexType=self.val.type.template_argument(1)
      entryType=valueType
      attr=None
      
      if valueType.tag:
         m=self.entryTypeName.search(valueType.tag)
         if m:
            name=m.group(1)
            attr=name[0].lower()+name[1:]+"_"
            for a in valueType.fields():
               if a.name==attr:
                  valueType=a.type
                  break
      self.iter=self.Iter(self.val, entryType, valueType, attr, indexType)

      return "HASH "+typeToStr(valueType)+"["+typeToStr(indexType) \
                      +"], members:"+str(self.val['members_'])+", V:" \
                      +str(self.val['versionAndFixed_']&0x7fff)

   def children(self):
      return self.iter

   def display_hint (self):
        return 'map'

class TacRbTreeMap:
   "Print a RbTreeMap"
   entryTypeName=re.compile('\\bTac([A-Z][a-zA-Z0-9_]*)$')

   class Iter:
      def __init__(self, val, entryType, valueType, attr, indexType):
         global char_pointer_type
         self.val=val
         self.members=val['members_']
         self.root=val['root_']['rawPtr_'].cast(entryType.pointer())
         self.entryType=entryType
         self.valueType=valueType
         self.attr=attr
         self.indexType=indexType
         t=self.root.dereference()['tacRbTreeMapElement_']
         self.offset=t.address.cast(char_pointer_type) \
                         -self.root.cast(char_pointer_type)

         self.current=self.findLeftmost(self.root)
         self.key=0
         self.cnt=0
         self.indexAttr = None
         if self.entryType==self.valueType:
            r=findAttrOfType(self.entryType,indexType)
            if len(r)==1:
               self.indexAttr=r[0]
            else:
               self.indexAttr=None

      def findLeftmost(self, r):
         while r:
            l=r
            r=r.dereference()['tacRbTreeMapElement_']['tacLeft_']['rawPtr_'] \
                            .cast(self.entryType.pointer())
            if r==0:
               return l

      def findNextElement(self, r):
         while r:
            l=r
            r=r.dereference();
            right=r['tacRbTreeMapElement_']['tacRight_']['rawPtr_'] \
                            .cast(self.entryType.pointer())
            if right!=0:
               return self.findLeftmost(right)

            while True:
               parent=r['tacRbTreeMapElement_']['tacParent_']
               if not parent:
                  return parent
               parent=(parent.cast(char_pointer_type)
                               -self.offset).cast(self.entryType.pointer())
               if parent['tacRbTreeMapElement_']['tacRight_']['rawPtr_']!=l:
                  return parent
               l=parent
               r=parent.dereference()

      def __iter__(self):
         return self

      def next(self):
         if not self.current:
            raise StopIteration
         if self.key==0:
            c=self.current.cast(self.entryType.pointer()).dereference()
            self.key=1
            if self.indexAttr:
               return ("KEY",c[self.indexAttr])
            if "tac_index_" in [x.name for x in self.entryType.fields()]:
               return ("KEY", c["tac_index_"])
            else:
               return ("KEY",nameForVal(c))
         else:
            r=self.current
            self.current=self.findNextElement(r)

            self.key=0
            if (self.entryType==self.valueType 
                     or not gdb.parameter("print taccDetails")):
               return ("VALUE",r.cast(self.entryType.pointer()))
            else:
               return ("VALUE",str(r.cast(self.entryType.pointer())[self.attr]))

      def __next__(self):
         return self.next()

   def __init__ (self, val):
      self.val = val

   def to_string (self):
      valueType=self.val.type.template_argument(0)
      indexType=self.val.type.template_argument(1)
      entryType=valueType
      attr=None
      if valueType.tag:
         m=self.entryTypeName.search(valueType.tag)
         if m:
            name=m.group(1)
            attr=name[0].lower()+name[1:]+"_"
            for a in valueType.fields():
               if a.name==attr:
                  valueType=a.type
                  break

      self.iter=self.Iter(self.val, entryType, valueType, attr, indexType)

      return "ORDERED "+typeToStr(valueType)+"["+typeToStr(indexType) \
                      +"], members:"+str(self.val['members_'])+", V:" \
                      +str(self.val['version_'])

   def children(self):
      return self.iter

   def display_hint (self):
        return 'map'

hashMapIterRe=re.compile("Tac::HashMap<.*>::Iterator(Const)?")
genericIterRe=re.compile("Tac::.*>::Iterator(Const)?")


class TacDensePtrQueue:
   """Print a DensePtrQueue"""

   class Iter:
      def __init__(self, val, ptrType, ptrTypeConst):
         self.val = val
         self.ptrType = ptrType
         self.ptrTypeConst = ptrTypeConst

         valType = val.type
         while valType.code==gdb.TYPE_CODE_TYPEDEF:
            valType = valType.strip_typedefs()
         
         dtname = str(valType)+"::Data"
         dataType = gdb.lookup_type(dtname)
         self.data = val['data_']['rawPtr_']
         self.data = self.data.cast(dataType.pointer())
         self.dataBytes = self.data['dataBytes_']
         self.dataArray = self.data['data_']

         bitmask = self.data['dataBytesBits__']
         try:
            self.entries = (self.dataBytes&bitmask) / self.ptrType.sizeof
            # Mimic Tac::DensePtrColl::entries()
         except RuntimeError:
            self.entries = 0
            # Null data_ member

         self.key = 0
         self.isPrintingKey = True

      def __iter__(self):
         return self

      def next(self):
         if self.key==self.entries:
            raise StopIteration
         if self.isPrintingKey:
            self.isPrintingKey = False
            return ("KEY",str(self.key))
         else:
            currentKey = self.key
            self.key = self.key + 1
            self.isPrintingKey = True
            return ("VALUE",str(self.dataArray[currentKey]))

      def __next__(self):
         return self.next()

   def __init__(self, val):
      self.val = val

   def to_string(self):
      ptrType = self.val.type.template_argument(0)
      ptrTypeConst = self.val.type.template_argument(1)
      self.iter = self.Iter(self.val, ptrType, ptrTypeConst)

      return "DENSE_PTR_QUEUE("+typeToStr(ptrType)+") members:"+str(self.iter.entries)

   def children(self):
      return self.iter

   def display_hint(self):
        return 'map'

def isTacObject(type):
   if not type:
      return False
   if type.code not in [gdb.TYPE_CODE_UNION, gdb.TYPE_CODE_STRUCT, gdb.TYPE_CODE_ENUM]:
      return False
   if str(type)=="Tac::VFPtrInterface" or str(type)=="Tac::Entity" or str(type).find("Notifiee")!=-1:
      # FixMe: There are hacks here due to GDB being full of lies
      return True
   return isTacObject(baseType(type))
   

def isTacNotifiee(type):
   # Return true if 'type' is a notifiee/reactor.
   if not type:
      return False
   if 'notifier_' in [x.name for x in type.fields()] or "Notifiee" in str(type):
      # FixMe: More hacks due to inheritance heirarchy not always showing up
      return True
   
   if isTacNotifiee(baseType(type)):
      return True
   return False

def isTacSimpleValueType(type):
   """ Returns if this is a type with only one non-attribute field, which is named "value_"."""
   hasValue = False
   
   if type.code not in [gdb.TYPE_CODE_UNION, gdb.TYPE_CODE_STRUCT, gdb.TYPE_CODE_ENUM]:
      return False
   try:
      for f in type.fields():
         if f.name == "value_":
            #print 'hasValue'
            hasValue = True
         else:
            if str(f.type).find("AttributeId") == -1:
               #print f.name
               return False
      return hasValue
   except:
      return False

def val_to_type(val):
   t = val.type.unqualified()
   if t.code==gdb.TYPE_CODE_REF:
      t=t.target()
   try:
      tag=t.tag
      if not tag:
         tag=str(t.strip_typedefs())
   except:
      tag=None
   retn = None

   if tag==None:
      return None
   if "Iterator" in tag and len(t.fields())==1 and hashMapIterRe.match(str(t.fields()[0].type)):
      retn = TacHashMapIter(val.cast(t.fields()[0].type))
   if tag[0:26]=="Tac::StringN<unsigned char":
      retn = TacStringPrinter8(val)
   if tag=="Tac::Uri":
      retn = TacStringPrinter(val['str_'])
   if tag=="Tac::String8":
      retn = TacStringPrinter8(val)
   if tag=="Tac::String" or tag=="Tac::MutableString":
      retn = TacStringPrinter(val)
   if tag=="Tac::Name":
      retn = TacStringPrinter(val)
   if tag=="Tac::Entity" and not (gdb.parameter("print taccDetails")):
      retn = TacEntity(val.cast(val.type))
   if tag=="Tac::PtrInterface":
      retn = TacPtrInterface(val)
   if hashMapIterRe.match(tag):
      retn = TacHashMapIter(val)
   elif genericIterRe.match(tag):
      retn = None
   elif tag[0:13]=="Tac::ListRaw<":
      retn = TacRawList(val)
   elif tag[0:9]=="Tac::Ptr<":
      retn = TacSmartPtr(val)
   elif tag[0:15]=="Tac::RbTreeMap<":
      retn = TacRbTreeMap(val)
   elif tag[0:13]=="Tac::HashMap<":
      retn = TacHashMap(val)
   if tag[0:15]=="Tac::LinkQueue<":
      retn = TacLinkQueue(val)
   if tag[0:16]=="Tac::LinkedList<":
      retn = TacLinkedList(val)
   if tag[0:11]=="Tac::Array<":
      retn = TacArray(val)
   if tag[0:14]=="Tac::DynArray<":
      retn = TacDynArray(val)
   if tag[0:16]=="Tac::ArrayQueue<":
      retn = TacArrayQueue(val)
   if tag[0:19]=="Tac::DynArrayQueue<":
      retn = TacDynArrayQueue(val)
   if tag[0:15]=="Tac::LinkStack<":
      retn = TacLinkStack(val)
   if tag[0:22]=="Tac::RbTreeMapElement<":
      retn = TacRbTreeMapElement(val)
   if tag[0:27]=="Tac::DensePtrQueueTemplate<":
      retn = TacDensePtrQueue(val)
   if tag[0:13]=="Tac::Ordinal<" or tag[0:13]=="Tac::Nominal<" or isTacSimpleValueType(t):
      #FixMe: are the first two cases possible?
      retn = TacOrdinalNominal(val)
   if tag[-6:]=="RawPtr":
      retn = TacPointer(val)
   elif ((tag[-1:]=='*'  or tag[-7:] == "* const") and isTacObject(val.type.target())):
      retn = TacPointer(val)
   if tag=="Tac::EntityId":
      retn = TacEntityId(val)
   return retn
   
def tac_lookup_function(val):
   "find appropriate pretty printer."
   initTaccTypes()
   retn = val_to_type(val)
   try:
      if retn:
         str(retn)
      return retn
   except:
      pass

class FindInCollection(gdb.Function):
   """ Given a collection and a key, will return the key and value of the
   collection entry with that key.  Used by $find(collection, key) if the key is exact
   (this works best for literal keys and strings).  There is also $find(collection, key, 1),
   which will do an 'approximate' search, where the key is a string, and the result
   is the first key-value pair where 'key' is a substring of the stringified key. """
   
   def __init__(self):
      super(FindInCollection,self).__init__("find")

   def invoke(self, hash, key,approximate=False):
      v = val_to_type(hash)
      v.to_string()
      try : 
         s = v.iter.next()
         if approximate:
            while( (str(key)[1:-1] not in str(s[1]).replace("\n","").replace("  ",""))):
               # Approximate takes a string, so you need to strip off the "
               
               v.iter.next()
               s = v.iter.next()
         else:
            while( (str(key) != str(s[1]))):
               v.iter.next()
               s = v.iter.next()
         if approximate:
            res = str(s[1]).replace("\n","").replace("  ","")
            s = v.iter.next()
            return res + " ::: " + str(s[1])
         s = v.iter.next()
         return s[1]
      except StopIteration:
         return "Value Not Found"
   
FindInCollection()

defaultBreakPointsFile = os.path.expanduser("~/.gdbBreakPoints")
# A default break point save file used by both SaveBreaks and LoadBreaks commands

class SaveBreaks(gdb.Command):
   """Save the current breakpoints in a file
If the command is passed an argument the ~/.gdbBreakPoints_<arg0> file will
be used to store the breakpoints. If no argument is passed, the default 
~/.gdbBreakPoints will be used. Existing break point files will be overridden.
   """
   def __init__(self):
      super(SaveBreaks,self).__init__(
         "saveBreaks",
         # Name of the command 
         gdb.COMMAND_BREAKPOINTS,
         gdb.COMPLETE_NONE,
         False)
         # This is not a prefix command. 

   def invoke(self,arg,from_tty):
      # Iterate over the current break points and save them to a known file.
      
      fileName = defaultBreakPointsFile
      if arg: 
         argv = gdb.string_to_argv(arg)
         if len(argv)>1:
            raise gdb.GdbError("function does not accept more than one argument")
         elif len(argv)==1:
            fileName = fileName+"_"+argv[0]

      if gdb.breakpoints():
         print("Saving breakpoints into file :",fileName)
         gdb.execute("save breakpoints "+fileName)
      else: 
         print("No breakpoints to save")

SaveBreaks()

class LoadBreaks(gdb.Command):
   """Load breakpoints from a well known file
If the command is passed an argument the ~/.gdbBreakPoints_<arg0> file will
be used to restore the breakpoints. If no argument is passed, the default 
~/.gdbBreakPoints will be used. Existing break points in the gdb context will be 
overridden
   """
   def __init__(self):
      super(LoadBreaks,self).__init__(
         "loadBreaks",
         # Name of the command 
         gdb.COMMAND_BREAKPOINTS,
         gdb.COMPLETE_NONE,
         False)
         # This is not a prefix command. 
   
   def invoke(self,arg,from_tty):
      # Iterate over the current break points and save them to a known file.
      
      fileName = defaultBreakPointsFile
      if arg: 
         argv = gdb.string_to_argv(arg)
         if len(argv)>1:
            raise gdb.GdbError("function does not accept more than one argument")
         elif len(argv)==1:
            fileName = fileName+"_"+argv[0]

      print("Loadting breakpoints from file :",fileName)
      gdb.execute("set confirm off")
      gdb.execute("delete") 
      # Delete the existing break points. 
      gdb.execute("source "+fileName)
      gdb.execute("set confirm on")
LoadBreaks()

class ShowProcessEnv(gdb.Command):
   """
   showProcessEnv [regexPattern]
Show the running process' environment. This is different from the gdb's
environment.  This command iterates over the x/s *((char **)environ+N)
commands up until the memory is not accessible. If the optional [regexPattern]
parameter is given, only the environment that matches the given regex will be 
printed the rest will be omitted. 
   """
   def __init__(self):
      super(ShowProcessEnv,self).__init__(
         "showProcessEnv",
         gdb.COMMAND_DATA,
         gdb.COMPLETE_NONE,
         False)
   
   def invoke(self,arg,from_tty):
      # Iterate over the running processes environment and print it so the gdb out. 
      # If a parameter is specified compile it to a regular expression and print 
      # only the matching ones.

      regexMatch = None
      if arg: 
         argv = gdb.string_to_argv(arg)
         if len(argv)>1:
            raise gdb.GdbError(
               "showProcessEnv does not expect mode than one argument")
         elif len(argv)==1:
            regexMatch = re.compile(argv[0])
            print("Searching for regex:",regexMatch.pattern,"in process' environment")

      i = 0
      while True:
         currentEnvVarPrint = gdb.execute(
            "x/s *((char **)environ +"+str(i)+")",
            False,
            True)
         if "Cannot access memory at address" in currentEnvVarPrint:
            # Reached the end of the process' envionment variable 
            break
         else:
            # print the currentEnvPrint of the stdout of the gdb
            if not regexMatch \
               or (regexMatch and regexMatch.search(currentEnvVarPrint)):
               # Regex is not specified 
               # or
               # Regex is specified and it matches with the current env var
               gdb.write(str(i)+": "+currentEnvVarPrint)
         i = i+1
ShowProcessEnv()

def checkForTaccProcess(commandName):
   # Some commands are supported only if we are debugging the tacc compiler. 
   # This function check that the program under debug is the tacc compiler and 
   # throws an exception otherwise 
   file = os.path.basename(gdb.current_progspace().filename)
   if file!="tacc": 
      raise gdb.GdbError(commandName
         +" is only supported during debugging the tacc compiler")

def checkTacomaTraversalCommandArg(cmdName,arg):
   # Command line parameter checking for commands that traverse tacoma. 
   # imperNode and constraint commands. 
   if not arg:
      raise gdb.GdbError(cmdName+" expects one argument for the path in tacoma")

   argv = gdb.string_to_argv(arg)
   if len(argv)!=1:
      raise gdb.GdbError(cmdName
         +" expects only one argument for the path in tacoma")

def splitPathComp(path):
   # Given a slash "/" separated path, split the companents and remove empty
   # components and return the list. 

   pathComps = path.split("/")
   pathComps = [p for p in pathComps if p!=""]
   # remove empty strings. They can appear at the beginning if the user 
   # has passed "/" at the start of the parameter to this command. 
   # The empty strings can also appear in other locations if the user 
   # has fat-fingered consecuitive "//" characters in path separation
   return pathComps

def splitParentPathAndPrefix(completeCmd,lastWord):
   # A handy function used in Command.complete function if the thing to be
   # completed is a Tac::PathName like path component. 
   # The completeCmd holds the complete command line up to the cursor's location. 
   # The lastWord holds the last word of the command line. 
   # This function returns the parentPath and the last prefix of the path. 

   assert completeCmd.endswith(lastWord)
   # This expectation is according to the documentation of Command.complete 
   # function in gdb python documentation. 

   parentPath = completeCmd.strip()
   prefix = lastWord 
   if parentPath.endswith("/"):
      prefix = ""
   else:
      parentPath = completeCmd[:len(parentPath)-len(prefix)]

   return [parentPath,prefix]

def traverseInTacoma(tacomaRootSymbolName,path):
   # Traverse the tacoma data structure with the given tacomaSymbolName and reach
   # the location given in path. 
   
      tacomaRootSymbol = gdb.lookup_global_symbol(tacomaRootSymbolName)

      if not tacomaRootSymbol.is_valid():
         raise gdb.GdbError("Cannot find "+tacomaRootSymbolName)

      tacomaRoot = tacomaRootSymbol.value()
      tacomaRootName = tacomaRoot["name_"]

      pathComps = splitPathComp(path)

      if len(pathComps)>0 and pathComps[0]==getString(tacomaRootName):
         del pathComps[0]
      # If the user has used the "GlobalScope" at the start of the passed parameter 
      # we can remove it. That is the tacoamRoot to start with 

      rv = tacomaRoot
      for pc in pathComps:
         # Itearate over all path components and get the pointers for 
         # each component. 
         accessorName = "type()" if rv==tacomaRoot else "dataMemberType_"
         # OGlobalScopeTypeAttr (otacomaRoot) is of OTacc::OTypeAttr, the other
         # lookups are OTacc::ImperNode. With respect to that  we need to change
         # the data member we are accessing to get the actual type to pass to
         # the ais function. 

         printedRv = str(rv).split()
         # A string like 
         # (OTacc::OTypeAttr *)0x500bedec /.../GlobalScope    OR 
         # (OTacc::ImperNode *)0x52866b30 /GlobalScope/MountTopTest
         ais = "ais(("+printedRv[0]+printedRv[1]+")->"+accessorName+",\""+pc+"\")"
         # A debug-only function in OTacc.cpp. Stands for Attribute In Scope.

         rv = gdb.parse_and_eval(ais)
         # Make the gdb call the ais function with correct parameters

         if int(rv.cast(gdb.lookup_type("int")))==0:
            # Cast the accessed value to int and compare it to NULL
            # If it is a null pointer, give a reasonable error message and return
            raise gdb.GdbError("Could not find "+pc);

      return rv


class ImperNode(gdb.Command):
   """
   imperNode pathInOTACOMA
   e.g: 
   imperNode /GlobalScope/MountTopTest/DerivedDerivedConstrainer/attrIs
   imperNode /MountTopTest/DerivedDerivedConstrainer/attrIs
   imperNode MountTopTest/DerivedDerivedConstrainer/attrIs

   Using the pathInOTACOMA recurse into the OTACOMA data structure and return 
   the pointer to the OTacc::ImperNode type at the pathInOTACOMA location.
   Supported only in tacc process"

   """
   def __init__(self):
      self.otacomaRootSymbolName = "OTacc::OGlobalScopeTypeAttr_"
      self.cmdName = "imperNode"
      super(ImperNode,self).__init__(
         self.cmdName,
         gdb.COMMAND_DATA)

   def complete(self,text,word):
      # Gdb uses the return value of this function to complete the parameter 
      # to imperNode. This function is executed once the user presses <TAB> while 
      # typing the argument for the command
      # Get the path to the parent, print the imperNode collection in it. 
      # Then return all the keys that have a word as prefix. 

      [parentPath,prefix] = splitParentPathAndPrefix(text,word)

      try:
         parent = traverseInTacoma(self.otacomaRootSymbolName,parentPath)
      except:
         pass

      imperNode = str(parent["constraint_"])

      candidates = []
      groupName = "key"
      regex = r"\[\"(?P<"+groupName+r">"+prefix+r".*)\"\]"
      # This matches the start of a line while printing hash tables.
      # For example :
      #  ["attr_"] = (OTacc::OConstraint *)0xd9d25f8 /GlobalScope/MountTopTest'/D..
      keyWithMatchingPrefix = re.compile(regex)

      for e in imperNode.splitlines():
         r = keyWithMatchingPrefix.search(e)
         if r:
            candidates.append(r.group(groupName))

      return candidates


   def invoke(self,arg,from_tty):
      # Look-up in the OTACOMA data structure for the OTacc::ImperNode node 
      # given in the argument list.
      checkForTaccProcess(self.cmdName)
      checkTacomaTraversalCommandArg(self.cmdName,arg)

      path = gdb.string_to_argv(arg)[0]

      rv = traverseInTacoma(self.otacomaRootSymbolName,path)

      print(rv)
ImperNode()

def globalDir():
   # Get the Tac::Dir::globalDir::ptr static pointer and return its 
   # equivalent gdb.value.
   # This function uses "info var <staticVariablePath>" gdb command to get the 
   # Tac::Dir::globalDir::ptr static variable in the process memeory.
   # Then dereferences that and returns the pointer for Tac::globalDir()
   
   globalDirPtrCmd = "info var Tac::Dir::globalDir()::ptr"
   infoVarRes = gdb.execute(globalDirPtrCmd,to_string=True)
   # Example output: 
   # All variables matching regular expression "Tac::Dir::globalDir()::ptr":
   #
   # Non-debugging symbols:
   # 0xf7fd6564  Tac::Dir::globalDir()::ptr
   #
   # Using gdb.execute to get the resulting strin.g 

   ptrGrpName = "ptr"
   ptrValRegex = r"^(?P<"+ptrGrpName \
      +">0x[0-9a-fA_F]+)\s+Tac::Dir::globalDir\(\)::ptr"
   # Match a line like :
   # 0xf7fd6564  Tac::Dir::globalDir()::ptr

   ptrValMatch = re.search(ptrValRegex,infoVarRes,re.MULTILINE)
   ptrVal = ptrValMatch.group(ptrGrpName)

   derefPtrCmd = "*(Tac::Dir **)"+ptrVal
   globalDir = gdb.parse_and_eval(derefPtrCmd)
   # Make gdb dereference the Tac::Dir** and get the gdb.value equivalent 
   # of Tac::globalDir()

   return globalDir

def traverseInGlobalDir(path):
   # Starting from the Tac::globalDir(), "/" traverse into the 
   # Tac::Dir::entityRef collections to find the entity at the given path. 
   # Return the gdb.value that corresponds to the entity located in path
   # If not found throw an gdb.Error exception.

   gD = globalDir()
   # FixMe: We can experiment with saving the globalDir and 
   # returning the cached value in future executions. 
   # The saved globalDir value needs to be cleared after re-executions of the 
   # program. globaldir does not change unless the programmer re-runs the 
   # program. 

   pathComps = splitPathComp(path)

   parent = gD
   currPath = "/"
   for pc in pathComps:
      currPath = currPath+"/"+pc
      # FixMe: We could use os.posixpath.join for this path manipulation.
      tacEntityCall = "Tac::entity(\""+currPath+"\")"
      parent = gdb.parse_and_eval(tacEntityCall)
      # FixMe: Here we rely on the Tac::entity call. 
      # This would not work in core file debugging. 
      # In core file debugging, there is not running process and we cannot 
      # execute Tac::entity. We should re-write this similar to the 
      # TacHashMap.Iter.next function. 
      if int(parent.cast(int_type))==0:
         raise gdb.GdbError("Could not find "+str(pc)+" in "+path)
      
      pType = parent.dynamic_type
      parent = parent.cast(pType)
      # FixMe: We rely on the entities to be of Tac::Dir type. 
      # This limits us with Tac::Dirs only. It would be great if we 
      # somehow could support all entity types and their sub attributes. 
      # This would look like the Acons command line then. 

   return parent

class Entity(gdb.Command):
   """
   A simple gdb command that can be used to traverse the object model in a tacc
   process. It starts from the Tac::globalDir(), "/" and traverses down
   the entityRef collections to find the desired entity. 
   """
   def __init__(self):
      self.cmdName = "entity"
      self.namePattern = r"^\s*\[\"(?P<name>.+)\"\]\s+=\s+.*$"
      # Example line:
      # ["Agents"] = (Tac::Dir::Entry *)0x50d2ea0c /Agents, ptr =
      # (Tac::Entity *)0x50d23d34 /Agents (SmartPtr),
      # Match the key portion of this line. 
      self.nameRegex = re.compile(self.namePattern,re.MULTILINE)
      # Pre assign the regex matcher used to find completion candidates. 
      super(Entity,self).__init__(
         self.cmdName,
         gdb.COMMAND_DATA)

   def checkCommandArg(self,arg):
      # Check the command line arguments for the Entity command. 
      # We only expect one argument. 
      if not arg:
         raise gdb.GdbError(self.cmdName+" expects one argument as a path")

      argv = gdb.string_to_argv(arg)
      if len(argv)!=1:
         raise gdb.GdbError(self.cmdName
            +" expects only one argument for an entity path")


   def complete(self,text,word):
      # Return the set of possible candidates while recursing one level down 
      # in the Tac::Dir directory structure. 

      [parentPath,prefix] = posixpath.split(text)

      try:
         p = traverseInGlobalDir(parentPath)
      except gdb.GdbError as e: 
         print("traveverseinGlobalDir returned error:",str(e),"for path:",
            str(parentPath))
         return []

      entryState = str(p["entryState_"])
      allMatches = self.nameRegex.findall(entryState)
      # Extract all the keys from the entryState output. 
      # We expect an output like this: 
      # ["Transact"] = (Tac::Dir::Entry *)0x50ce8f24 /Transact, ptr =
      # (Tac::Entity *)0x50ce92bc /Transact (SmartPtr),
      # ["activities"] = (Tac::Dir::Entry *)0x86c25c8 /activities, ptr =
      # (Tac::Entity *)0x86c2630 /activities (SmartPtr),
      # We extract all the keys in the entityRef collection to a list. 
      returnValue = [m for m in allMatches if m.startswith(prefix)]
      # Do some prefix matching
      return returnValue


   def invoke(self,arg,from_tty):
      # Starting from the Tac::globalDir(), "/" traverse into the 
      # Tac::Dir::entityRef collections to find the entity at the given path. 

      self.checkCommandArg(arg)
      path = gdb.string_to_argv(arg)[0]
      rv = traverseInGlobalDir(path)
      print(str(rv))
      return rv
      # FixMe: How to save the result of this call to a convenience variable. 


Entity()

# FixMe: This tacgdb file is getting very long. 
# We can separate the Commands to antoher tacgdbCommands.py file. 



gdb.pretty_printers = [tac_lookup_function]

# vim: set ft=python:
