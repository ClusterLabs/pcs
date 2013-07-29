class PCSDWizard
  def self.getchildren
    classes=[]
    ObjectSpace.each_object do |klass|
      next unless Module === klass
      classes << klass if PCSDWizard > klass
    end
    classes
  end

  def self.getAllWizards
    getchildren
  end

  def self.getWizard(wizard)
    getchildren.each {|c|
      if c.to_s == wizard.to_s
	return Object.const_get(wizard.to_s).new
      end
    }
    return nil
  end
end
