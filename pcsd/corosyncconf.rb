module CorosyncConf
  class Section
    attr_reader :parent, :name

    def initialize(name)
      @parent = nil
      @attr_list = []
      @section_list = []
      @name = name
    end

    def text(indent='    ')
      lines = []
      @attr_list.each { |attrib|
        lines << "#{attrib[0]}: #{attrib[1]}"
      }
      lines << '' if not(@attr_list.empty? or @section_list.empty?)
      last_section = @section_list.length - 1
      @section_list.each_with_index { |section, index|
        lines += section.text.split("\n")
        lines.pop if lines[-1].strip.empty?
        lines << '' if index < last_section
      }
      if @parent
        lines.map! { |item| item.empty? ? item : indent + item }
        lines.unshift("#{@name} {")
        lines << '}'
      end
      final = lines.join("\n")
      final << "\n" if not final.empty?
      return final
    end

    def root
      parent = self
      parent = parent.parent while parent.parent
      return parent
    end

    def attributes(name=nil)
      return @attr_list.find_all { |attrib| not name or attrib[0] == name }
    end

    def add_attribute(name, value)
      @attr_list << [name, value]
      return self
    end

    def del_attribute(attribute)
      @attr_list.delete(attribute)
      return self
    end

    def del_attributes_by_name(name, value=nil)
      @attr_list.reject! { |attrib|
        attrib[0] == name and (not value or attrib[1] == value)
      }
      return self
    end

    def set_attribute(name, value)
      found = false
      new_attr_list = []
      @attr_list.each { |attrib|
        if attrib[0] != name
          new_attr_list << attrib
        elsif not found
          found = true
          attrib[1] = value
          new_attr_list << attrib
        end
      }
      @attr_list = new_attr_list
      self.add_attribute(name, value) if not found
      return self
    end

    def sections(name=nil)
      return @section_list.find_all { |section|
        not name or section.name == name
      }
    end

    def add_section(section)
      parent = self
      while parent
        raise CircularParentshipException if parent == section
        parent = parent.parent
      end
      section.parent.del_section(section) if section.parent
      section.parent = self
      @section_list << section
      return self
    end

    def del_section(section)
      if @section_list.delete(section)
        # don't set parent to nil if the section was not found in the list
        section.parent = nil
      end
      return self
    end

    protected

    def parent=(parent)
      @parent = parent
      return self
    end
  end


  def CorosyncConf::parse_string(conf_text)
    root = Section.new('')
    self.parse_section(conf_text.split("\n"), root)
    return root
  end

  def CorosyncConf::parse_section(lines, section)
    # parser is trying to work the same way as an original corosync parser
    while not lines.empty?
      current_line = lines.shift().strip()
      next if current_line.empty? or current_line.start_with?('#')
      if current_line.include?('{')
        section_name = current_line.rpartition('{').first
        new_section = Section.new(section_name.strip)
        section.add_section(new_section)
        self.parse_section(lines, new_section)
      elsif current_line.include?('}')
        if not section.parent
          raise ParseErrorException, 'Unexpected closing brace'
        end
        return
      elsif current_line.include?(':')
        section.add_attribute(
          *current_line.split(':', 2).map { |part| part.strip }
        )
      end
    end
    raise ParseErrorException, 'Missing closing brace' if section.parent
  end


  class CorosyncConfException < Exception
  end

  class CircularParentshipException < CorosyncConfException
  end

  class ParseErrorException < CorosyncConfException
  end
end
